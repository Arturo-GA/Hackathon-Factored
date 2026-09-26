"""Verificación independiente (parte 5): histograma diario de brechas 0-60 d (observado vs media de
24 permutaciones dentro de producto) para buscar picos en 28-31 d; concentración de los pares 27-33 d
de los 2 comercios marcados; ¿la mezcla de comercios cambia en el tiempo (año, mes del año)?"""
import time
import duckdb
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 200)

con = duckdb.connect("data/analysis.duckdb", read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

con.execute("""CREATE TEMP TABLE base AS
  SELECT transaction_id, product_id, ts, amount, merchant_name,
         row_number() OVER (PARTITION BY product_id ORDER BY ts, transaction_id) rn_t
  FROM tx WHERE merchant_name IS NOT NULL""")

DAYS = """WITH s AS (SELECT merchant_name, ts, lag(ts) OVER (PARTITION BY product_id, merchant_name ORDER BY ts) pts FROM {tab}),
  g AS (SELECT merchant_name, date_diff('day', pts, ts) gap FROM s WHERE pts IS NOT NULL)
  SELECT merchant_name IN ('Estación de Servicio','Óptica Visión') flagged, least(gap, 999) gap, count(*) n FROM g GROUP BY ALL"""
obs = q(DAYS.format(tab="base")); obs["src"] = "obs"
res = [obs]
t0 = time.time()
NP = 24
for i in range(NP):
    con.execute(f"""CREATE OR REPLACE TEMP TABLE perm AS
      WITH r AS (SELECT product_id, merchant_name,
                  row_number() OVER (PARTITION BY product_id ORDER BY hash(transaction_id || 'd{i}')) rn_r FROM base)
      SELECT a.product_id, a.ts, r.merchant_name FROM base a JOIN r ON a.product_id=r.product_id AND a.rn_t=r.rn_r""")
    d = q(DAYS.format(tab="perm")); d["src"] = f"p{i}"
    res.append(d)
    con.execute("DROP TABLE perm")
print(f"{NP} permutaciones en {time.time()-t0:.0f}s")
allr = pd.concat(res)


def summarize(df, title, lo=20, hi=40):
    t = df.groupby(["src", "gap"]).n.sum().unstack("src").fillna(0)
    nulls = t.drop(columns="obs")
    out = pd.DataFrame({"obs": t.obs, "null_mean": nulls.mean(axis=1), "null_sd": nulls.std(axis=1, ddof=1)})
    out["ratio"] = out.obs / out.null_mean
    out["z"] = (out.obs - out.null_mean) / out.null_sd
    print(f"\n== {title}: brechas diarias {lo}-{hi} ==")
    print(out.loc[lo:hi].round(2).T.to_string())
    # ventana 27-33 como estadístico agregado, con SD del nulo por permutación
    w = t.loc[27:33].sum()
    nw = w.drop("obs")
    print(f"27-33 d: obs={w.obs:.0f} nulo={nw.mean():.1f}±{nw.std(ddof=1):.1f}  razón={w.obs/nw.mean():.3f} z={(w.obs-nw.mean())/nw.std(ddof=1):.2f}  "
          f"p_emp(nulo>=obs)={(nw>=w.obs).mean():.3f}")
    w2 = t.loc[28:31].sum(); nw2 = w2.drop("obs")
    print(f"28-31 d: obs={w2.obs:.0f} nulo={nw2.mean():.1f}±{nw2.std(ddof=1):.1f}  razón={w2.obs/nw2.mean():.3f} z={(w2.obs-nw2.mean())/nw2.std(ddof=1):.2f}")
    # chi2 global de 0-60 + resto contra la media del nulo (aprox.)
    tt = t.copy(); tt.index = np.where(tt.index <= 60, tt.index, 61)
    tt = tt.groupby(level=0).sum()
    nm = tt.drop(columns="obs").mean(axis=1)
    sd = tt.drop(columns="obs").std(axis=1, ddof=1)
    zz = (tt.obs - nm) / sd
    print(f"bins 0..60 + >60: max|z|={zz.abs().max():.2f} en gap={zz.abs().idxmax()}  #|z|>3 = {(zz.abs()>3).sum()} de {len(zz)}")


summarize(allr, "Todos los comercios")
summarize(allr[allr.flagged], "Estación de Servicio + Óptica Visión")
summarize(allr[~allr.flagged], "Resto (22 comercios)")

print("\n== Pares 27-33 d de los 2 comercios marcados: ¿concentrados en pocos productos/clientes? ==")
print(q("""WITH s AS (SELECT product_id, merchant_name, ts, amount, lag(ts) OVER (PARTITION BY product_id, merchant_name ORDER BY ts) pts,
             lag(amount) OVER (PARTITION BY product_id, merchant_name ORDER BY ts) pamt FROM base
           WHERE merchant_name IN ('Estación de Servicio','Óptica Visión'))
  SELECT merchant_name, count(*) n_pairs, count(DISTINCT product_id) n_prod, median(abs(amount/pamt-1)) med_rel_amt_diff,
         avg((day(ts)=day(pts))::INT) p_same_dom, min(ts) first_ts, max(ts) last_ts
  FROM s WHERE date_diff('day', pts, ts) BETWEEN 27 AND 33 GROUP BY 1""").to_string(index=False))

print("\n== ¿La mezcla de comercios varía en el tiempo? V de Cramér comercio x año y comercio x mes-del-año ==")
for expr, nm in [("year(ts)", "año"), ("month(ts)", "mes"), ("strftime(ts, '%Y-%m')", "año-mes"), ("dayofweek(ts)", "día semana")]:
    ct = q(f"SELECT {expr} k, merchant_name, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2")
    tab = ct.pivot_table(index="merchant_name", columns="k", values="n", fill_value=0).values
    chi2, pv, dof, _ = chi2_contingency(tab)
    n = tab.sum(); V = (chi2 / (n * (min(tab.shape) - 1))) ** 0.5
    print(f"comercio x {nm}: chi2={chi2:.1f} dof={dof} p={pv:.3g} V={V:.4f}")
