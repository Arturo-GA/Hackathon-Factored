"""Verificación independiente: behavior_enlaces_cruzados_rotos.
(A) tx -> pr: dueño y moneda.  (B) cc.mentioned_products: existencia en pr y pertenencia al cliente que llama.
(C) de.product_id (POBLACIÓN COMPLETA, no muestra): existencia y pertenencia.
(D) cp.claimed: coincidencia exacta/aproximada con tx del mismo cliente vs placebo; cobertura por azar;
    distribución por moneda (KS vs U(50,5000)); moneda del reclamo vs país y vs monedas de productos del cliente."""
import duckdb
import numpy as np
import pandas as pd
from scipy import stats

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()


def cramers_v(ct):
    chi2 = stats.chi2_contingency(ct, correction=False)[0]
    n = ct.values.sum()
    r, k = ct.shape
    return np.sqrt(chi2 / (n * (min(r, k) - 1)))


print("=== (A) tx -> pr ===")
print(Q("""SELECT count(*) n_tx, count(p.product_id) tx_con_producto_en_pr,
           sum((t.customer_id = p.customer_id)::INT) mismo_duenio,
           sum((t.currency = p.currency)::INT) misma_moneda
           FROM tx t LEFT JOIN pr p USING (product_id)""").to_string(index=False))

print("\n=== (B) cc.mentioned_products ===")
con.execute("""CREATE TEMP TABLE m AS
  SELECT interaction_id, customer_id, upper(trim(x)) pid
  FROM (SELECT interaction_id, customer_id, unnest(string_split(mentioned_products, ',')) x
        FROM cc WHERE mentioned_products IS NOT NULL) WHERE trim(x) <> ''""")
print(Q("""SELECT (SELECT count(*) FROM cc) n_cc, (SELECT count(mentioned_products) FROM cc) cc_con_menciones,
           count(*) n_menciones, count(DISTINCT pid) n_pid_distintos,
           avg(regexp_full_match(pid, 'PRD-[A-Z0-9]{12}')::INT) formato_ok FROM m""").to_string(index=False))
con.execute("CREATE TEMP TABLE prk AS SELECT product_id, customer_id own_cust, ptype, pstatus FROM pr")
print(Q("""SELECT count(*) n_menciones, count(p.product_id) existe_en_pr,
           round(100.0*count(p.product_id)/count(*),3) pct_existe,
           sum((p.own_cust = m.customer_id)::INT) del_cliente_que_llama,
           sum((p.own_cust <> m.customer_id)::INT) de_otro_cliente
           FROM m LEFT JOIN prk p ON p.product_id = m.pid""").to_string(index=False))
# ¿el que llama tiene productos? (para descartar que 0% sea porque no tiene productos)
print(Q("""SELECT avg((EXISTS (SELECT 1 FROM prk p WHERE p.own_cust = c.customer_id))::INT) frac_llamadas_cliente_con_productos
           FROM (SELECT DISTINCT interaction_id, customer_id FROM m) c""").to_string(index=False))
# a nivel llamada: ¿alguna mención es del cliente?
print(Q("""SELECT count(*) llamadas, sum(any_own::INT) llamadas_con_alguna_mencion_propia FROM (
           SELECT m.interaction_id, bool_or(coalesce(p.own_cust = m.customer_id, false)) any_own
           FROM m LEFT JOIN prk p ON p.product_id = m.pid GROUP BY 1)""").to_string(index=False))
# ¿los IDs mencionados aparecen en otras tablas?
print(Q("""WITH d AS (SELECT DISTINCT pid FROM m)
           SELECT count(*) pid_distintos,
             sum((pid IN (SELECT DISTINCT product_id FROM tx))::INT) en_tx,
             sum((pid IN (SELECT DISTINCT product_id FROM de WHERE product_id IS NOT NULL))::INT) en_de,
             sum((pid IN (SELECT DISTINCT affected_product_id FROM cp WHERE affected_product_id IS NOT NULL))::INT) en_cp
           FROM d""").to_string(index=False))

print("\n=== (C) de.product_id (población completa) ===")
print(Q("""SELECT count(*) eventos_con_pid, count(d.customer_id) con_pid_y_cliente,
           count(p.product_id) pid_existe_en_pr,
           sum(CASE WHEN d.customer_id IS NOT NULL AND p.product_id IS NOT NULL THEN 1 ELSE 0 END) existe_y_hay_cliente,
           sum((p.own_cust = d.customer_id)::INT) del_cliente_del_evento
           FROM de d LEFT JOIN prk p ON p.product_id = d.product_id
           WHERE d.product_id IS NOT NULL""").to_string(index=False))
print(Q("""SELECT (SELECT count(*) FROM de) n_de, (SELECT count(product_id) FROM de) de_con_pid,
           (SELECT count(*) FROM de WHERE product_id IS NOT NULL AND customer_id IS NOT NULL) de_con_pid_y_cliente""").to_string(index=False))

print("\n=== (D) cp.claimed ===")
con.execute("""CREATE TEMP TABLE cl AS SELECT complaint_id, customer_id, ts, category, subcategory, currency, claimed,
               CAST(round(claimed*100) AS BIGINT) cents FROM cp WHERE claimed IS NOT NULL""")
print(Q("""SELECT (SELECT count(*) FROM cp) n_cp, count(*) claimed_no_nulo, min(claimed) mn, max(claimed) mx,
           count(DISTINCT customer_id) clientes, count(currency) con_moneda FROM cl""").to_string(index=False))
con.execute("""CREATE TEMP TABLE txc AS SELECT t.customer_id, t.ts, t.amount, t.amount_usd, t.currency tcur,
               CAST(round(t.amount*100) AS BIGINT) cents, CAST(round(t.amount_usd*100) AS BIGINT) cents_usd
               FROM tx t WHERE t.customer_id IN (SELECT DISTINCT customer_id FROM cl)""")
print(Q("SELECT count(*) tx_de_reclamantes, count(DISTINCT customer_id) reclamantes_con_tx FROM txc").to_string(index=False))
# placebo: cada reclamo emparejado con el cliente de otro reclamo (permutación determinista)
con.execute("""CREATE TEMP TABLE clp AS SELECT c.*, lead(customer_id, 1, first_cust) OVER (ORDER BY hash(complaint_id)) other
               FROM (SELECT *, first_value(customer_id) OVER (ORDER BY hash(complaint_id)) first_cust FROM cl) c""")
res = {}
for lab, col in [('propio', 'customer_id'), ('placebo', 'other')]:
    res[lab] = Q(f"""SELECT count(*) n,
        sum(exact_amt::INT) exacto_amount, sum(exact_usd::INT) exacto_amount_usd,
        sum(near1::INT) cerca_1pct, sum(near01::INT) cerca_0_1pct FROM (
          SELECT c.complaint_id,
            coalesce(bool_or(t.cents = c.cents), false) exact_amt,
            coalesce(bool_or(t.cents_usd = c.cents), false) exact_usd,
            coalesce(bool_or(abs(t.amount - c.claimed) <= 0.01*c.claimed OR abs(t.amount_usd - c.claimed) <= 0.01*c.claimed), false) near1,
            coalesce(bool_or(abs(t.amount - c.claimed) <= 0.001*c.claimed OR abs(t.amount_usd - c.claimed) <= 0.001*c.claimed), false) near01
          FROM clp c LEFT JOIN txc t ON t.customer_id = c.{col} GROUP BY 1)""")
    res[lab].insert(0, 'emparejamiento', lab)
print(pd.concat(res.values()).to_string(index=False))
# placebo: tx de 'other' no están en txc si other no tiene tx; está bien (txc cubre a todos los reclamantes).
# coincidencia exacta con CUALQUIER tx (cualquier cliente) y cobertura por azar
con.execute("CREATE TEMP TABLE allc AS SELECT DISTINCT CAST(round(amount*100) AS BIGINT) cents FROM tx")
mnmx = Q("SELECT min(cents) a, max(cents) b FROM cl").iloc[0]
a, b = int(mnmx.a), int(mnmx.b)
print(Q(f"""SELECT (SELECT count(*) FROM cl) n_claims,
            (SELECT count(*) FROM cl WHERE cents IN (SELECT cents FROM allc)) match_cualquier_tx,
            (SELECT count(*) FROM allc WHERE cents BETWEEN {a} AND {b}) valores_cubiertos, {b - a + 1} valores_posibles""").to_string(index=False))

# distribución por moneda
cd = Q("SELECT currency, claimed FROM cl")
rows = []
for cur, g in cd.groupby(cd.currency.fillna('NULL')):
    x = g.claimed.values
    ks = stats.kstest(x, 'uniform', args=(50, 4950))
    rows.append(dict(moneda=cur, n=len(x), min=x.min(), p25=np.percentile(x, 25), mediana=np.median(x),
                     p75=np.percentile(x, 75), max=x.max(), KS_D=ks.statistic, KS_p=ks.pvalue))
print(pd.DataFrame(rows).round(3).to_string(index=False))
print("KS entre monedas (USD vs COP/ARS/MXN):")
for cur in ['COP', 'ARS', 'MXN']:
    if cur in set(cd.currency):
        r = stats.ks_2samp(cd.claimed[cd.currency == 'USD'], cd.claimed[cd.currency == cur])
        print(f"  USD vs {cur}: D={r.statistic:.4f} p={r.pvalue:.3g}")
print("Escala real de tx por moneda (mediana amount):")
print(Q("SELECT currency, count(*) n, median(amount) med_amount, quantile_cont(amount, 0.9) p90 FROM tx GROUP BY 1 ORDER BY 1").to_string(index=False))

# moneda del reclamo vs país del cliente
ct = Q("""SELECT u.country, c.currency, count(*) n FROM cp c JOIN cu u USING (customer_id)
          WHERE c.currency IS NOT NULL GROUP BY 1,2""").pivot(index='country', columns='currency', values='n').fillna(0)
print((ct.div(ct.sum(1), axis=0) * 100).round(1).assign(n=ct.sum(1)).to_string())
print("V de Cramér país x moneda reclamo:", round(cramers_v(ct), 4))
print(Q("SELECT count(*) n_cp, count(currency) con_moneda, count(claimed) con_monto, sum((claimed IS NOT NULL AND currency IS NULL)::INT) monto_sin_moneda FROM cp").to_string(index=False))
# moneda del reclamo ∈ monedas de productos del cliente (vs base: misma prueba con moneda al azar)
print(Q("""WITH pc AS (SELECT customer_id, list(DISTINCT currency) ccys FROM pr GROUP BY 1)
           SELECT c.currency, count(*) n,
             round(avg(coalesce(list_contains(pc.ccys, c.currency), false)::INT), 4) en_monedas_de_sus_productos
           FROM cp c LEFT JOIN pc USING (customer_id) WHERE c.currency IS NOT NULL GROUP BY 1 ORDER BY 1""").to_string(index=False))
print(Q("""SELECT u.country, p.currency, count(*) n FROM pr p JOIN cu u USING (customer_id) GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False))
