"""Verificación independiente (intento 3) de behavior_enlaces_cruzados_rotos. Parte 2: cp.claimed.
(D0) volumen; (D1) coincidencia exacta al centavo con tx del mismo cliente (amount y amount_usd) vs placebo (cliente de otro reclamo);
(D2) coincidencia aproximada +-1% / +-0.1% vs placebo; (D3) coincidencia con CUALQUIER tx vs cobertura por azar y vs placebo de
desplazamiento +-1 centavo; (D4) distribución por moneda (KS vs U(50,5000)); (D5) moneda del reclamo vs país (V de Cramér);
(D6) claimed vs tx del affected_product_id; (D7) moneda del reclamo vs monedas de productos del cliente."""
import sys, time
import duckdb
import numpy as np
import pandas as pd
from scipy import stats
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()
t0 = time.time()


def P(title, df):
    print(f"\n--- {title} [{time.time()-t0:.0f}s]")
    print(df.to_string(index=False))
    sys.stdout.flush()


P("D0: volumen", Q("""SELECT count(*) n_cp, count(claimed) claimed_no_nulo, count(currency) moneda_no_nula,
   sum((claimed IS NOT NULL AND currency IS NULL)::INT) monto_sin_moneda, sum((claimed IS NULL AND currency IS NOT NULL)::INT) moneda_sin_monto,
   min(claimed) mn, max(claimed) mx, count(DISTINCT CASE WHEN claimed IS NOT NULL THEN customer_id END) clientes_reclamantes FROM cp"""))

con.execute("""CREATE TEMP TABLE cl AS SELECT complaint_id, customer_id, ts, currency, claimed, affected_product_id,
               CAST(round(claimed*100) AS BIGINT) cents FROM cp WHERE claimed IS NOT NULL""")
# placebo: cliente de otro reclamo (permutación determinista por hash)
con.execute("""CREATE TEMP TABLE clp AS SELECT *, coalesce(lead(customer_id, 101) OVER (ORDER BY hash(complaint_id || 'v3')),
               first_value(customer_id) OVER (ORDER BY hash(complaint_id || 'v3'))) plac FROM cl""")
P("placebo != real", Q("SELECT count(*) n, sum((plac = customer_id)::INT) plac_igual_real FROM clp"))
con.execute("""CREATE TEMP TABLE tq AS SELECT customer_id, product_id, ts, amount, amount_usd, currency tcur,
               CAST(round(amount*100) AS BIGINT) c_amt, CAST(round(amount_usd*100) AS BIGINT) c_usd FROM tx
               WHERE customer_id IN (SELECT customer_id FROM clp UNION SELECT plac FROM clp)""")
P("tx de reclamantes (real+placebo)", Q("SELECT count(*) n_tx, count(DISTINCT customer_id) clientes FROM tq"))

rows = []
for lab, col in [('real', 'customer_id'), ('placebo', 'plac')]:
    r = Q(f"""SELECT '{lab}' emparejamiento, count(*) n_reclamos, sum(has_tx::INT) reclamante_con_tx, round(avg(ntx),1) tx_medias,
          sum(ex_amt::INT) exacto_amount, sum(ex_usd::INT) exacto_amount_usd,
          sum(ex_amt_pm1::INT) exacto_amount_desplazado_1c,
          sum(n1::INT) cerca_1pct, sum(n01::INT) cerca_0_1pct, sum(n1_90::INT) cerca_1pct_90d_previos
        FROM (SELECT c.complaint_id, count(t.customer_id) > 0 has_tx, count(t.customer_id) ntx,
            coalesce(bool_or(t.c_amt = c.cents), false) ex_amt,
            coalesce(bool_or(t.c_usd = c.cents), false) ex_usd,
            coalesce(bool_or(t.c_amt = c.cents + 1 OR t.c_amt = c.cents - 1), false) ex_amt_pm1,
            coalesce(bool_or(abs(t.amount - c.claimed) <= 0.01*c.claimed OR abs(t.amount_usd - c.claimed) <= 0.01*c.claimed), false) n1,
            coalesce(bool_or(abs(t.amount - c.claimed) <= 0.001*c.claimed OR abs(t.amount_usd - c.claimed) <= 0.001*c.claimed), false) n01,
            coalesce(bool_or((abs(t.amount - c.claimed) <= 0.01*c.claimed OR abs(t.amount_usd - c.claimed) <= 0.01*c.claimed)
                             AND t.ts < c.ts AND t.ts >= c.ts - INTERVAL 90 DAY), false) n1_90
          FROM clp c LEFT JOIN tq t ON t.customer_id = c.{col} GROUP BY 1)""")
    rows.append(r)
P("D1/D2: reclamo vs tx del mismo cliente (real) y de otro reclamante (placebo)", pd.concat(rows))

# D3: con cualquier tx
mm = Q("SELECT min(cents) a, max(cents) b FROM cl").iloc[0]
a, b = int(mm.a), int(mm.b)
con.execute(f"""CREATE TEMP TABLE allc AS SELECT DISTINCT CAST(round(amount*100) AS BIGINT) cents FROM tx
                WHERE amount BETWEEN {a/100 - 1} AND {b/100 + 1}""")
con.execute(f"""CREATE TEMP TABLE allu AS SELECT DISTINCT CAST(round(amount_usd*100) AS BIGINT) cents FROM tx
                WHERE amount_usd BETWEEN {a/100 - 1} AND {b/100 + 1}""")
P("D3: coincidencia con CUALQUIER tx (amount) vs cobertura y placebo de desplazamiento", Q(f"""
  SELECT count(*) n_reclamos,
    round(avg((cents IN (SELECT cents FROM allc))::INT),4) frac_match_exacto,
    round(avg((cents+1 IN (SELECT cents FROM allc))::INT),4) frac_match_mas1c,
    round(avg((cents-1 IN (SELECT cents FROM allc))::INT),4) frac_match_menos1c,
    round(avg((cents+37 IN (SELECT cents FROM allc))::INT),4) frac_match_mas37c,
    round((SELECT count(*) FROM allc WHERE cents BETWEEN {a} AND {b}) / ({b}-{a}+1.0),4) cobertura_azar_rango,
    round(avg((cents IN (SELECT cents FROM allu))::INT),4) frac_match_exacto_usd,
    round((SELECT count(*) FROM allu WHERE cents BETWEEN {a} AND {b}) / ({b}-{a}+1.0),4) cobertura_azar_usd
  FROM cl"""))
print(f"rango claimed en centavos: [{a}, {b}]")

# D4: distribución por moneda
cd = Q("SELECT coalesce(currency,'NULL') currency, claimed FROM cl")
out = []
for cur, g in cd.groupby('currency'):
    x = g.claimed.values
    ks = stats.kstest(x, 'uniform', args=(50, 4950))
    out.append(dict(moneda=cur, n=len(x), min=x.min(), p25=np.percentile(x, 25), mediana=np.median(x), p75=np.percentile(x, 75),
                    max=x.max(), KS_D=ks.statistic, KS_p=ks.pvalue))
P("D4: claimed por moneda (KS vs U(50,5000))", pd.DataFrame(out).round(3))
P("escala real de tx por moneda (para contraste)", Q("""SELECT currency, count(*) n, round(quantile_cont(amount,0.1),2) p10,
   round(median(amount),2) mediana, round(quantile_cont(amount,0.9),2) p90 FROM tx GROUP BY 1 ORDER BY 1"""))
P("claimed por categoría (mediana/rango)", Q("""SELECT category, count(claimed) n, round(min(claimed),2) mn, round(median(claimed),2) med,
   round(max(claimed),2) mx FROM cp GROUP BY 1 ORDER BY 2 DESC"""))

# D5: moneda vs país
for lab, filt in [('todos los reclamos con moneda', 'c.currency IS NOT NULL'),
                  ('solo claimed no nulo', 'c.currency IS NOT NULL AND c.claimed IS NOT NULL')]:
    ct = Q(f"""SELECT u.country, c.currency, count(*) n FROM cp c JOIN cu u USING (customer_id) WHERE {filt} GROUP BY 1,2""")
    ct = ct.pivot(index='country', columns='currency', values='n').fillna(0)
    chi2, p, dof, _ = stats.chi2_contingency(ct.values, correction=False)
    v = np.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))
    print(f"\n--- D5 ({lab}): % por fila; chi2={chi2:.1f} dof={dof} p={p:.3g} V de Cramér={v:.4f}")
    print((ct.div(ct.sum(axis=1), axis=0) * 100).round(1).assign(n=ct.sum(axis=1).astype(int)).to_string())

# D6: claimed vs tx del producto afectado (que es de otro cliente)
con.execute("""CREATE TEMP TABLE cla AS SELECT c.*, coalesce(lead(affected_product_id, 101) OVER (ORDER BY hash(complaint_id || 'p3')),
               first_value(affected_product_id) OVER (ORDER BY hash(complaint_id || 'p3'))) plac_prod
               FROM cl c WHERE affected_product_id IS NOT NULL""")
con.execute("""CREATE TEMP TABLE tp AS SELECT product_id, ts, amount, amount_usd, CAST(round(amount*100) AS BIGINT) c_amt FROM tx
               WHERE product_id IN (SELECT affected_product_id FROM cla UNION SELECT plac_prod FROM cla)""")
rows = []
for lab, col in [('real', 'affected_product_id'), ('placebo', 'plac_prod')]:
    rows.append(Q(f"""SELECT '{lab}' emparejamiento, count(*) n_reclamos, sum(has_tx::INT) producto_con_tx,
          sum(ex::INT) exacto, sum(n1::INT) cerca_1pct, sum(n01::INT) cerca_0_1pct FROM (
          SELECT c.complaint_id, count(t.product_id) > 0 has_tx, coalesce(bool_or(t.c_amt = c.cents), false) ex,
            coalesce(bool_or(abs(t.amount - c.claimed) <= 0.01*c.claimed OR abs(t.amount_usd - c.claimed) <= 0.01*c.claimed), false) n1,
            coalesce(bool_or(abs(t.amount - c.claimed) <= 0.001*c.claimed OR abs(t.amount_usd - c.claimed) <= 0.001*c.claimed), false) n01
          FROM cla c LEFT JOIN tp t ON t.product_id = c.{col} GROUP BY 1)"""))
P("D6: claimed vs tx del affected_product_id (real vs placebo)", pd.concat(rows))

# D7: moneda del reclamo en monedas de productos del cliente
P("D7: moneda del reclamo en monedas de los productos del cliente", Q("""
  WITH pc AS (SELECT customer_id, list(DISTINCT currency) ccys FROM pr GROUP BY 1)
  SELECT c.currency, count(*) n, round(avg(coalesce(list_contains(pc.ccys, c.currency), false)::INT),4) en_sus_productos
  FROM cp c LEFT JOIN pc USING (customer_id) WHERE c.currency IS NOT NULL GROUP BY 1 ORDER BY 1"""))
P("moneda de productos por país (contraste)", Q("""SELECT u.country, p.currency, count(*) n FROM pr p JOIN cu u USING (customer_id)
   GROUP BY 1,2 ORDER BY 1,2"""))
print(f"\nFIN parte 2 [{time.time()-t0:.0f}s]")
