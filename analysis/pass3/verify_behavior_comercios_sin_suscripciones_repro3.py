"""Verificación independiente (parte 3): nulo de permutación con varias semillas (media y DE),
secuencias tipo suscripción (>=2 brechas mensuales seguidas), ¿el monto depende del comercio?,
y umbral estricto <5% vs <=5% para comparar con el rango del hallazgo."""
import duckdb
import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 200)

con = duckdb.connect("data/analysis.duckdb", read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

con.execute("""CREATE TEMP TABLE base AS
  SELECT transaction_id, product_id, ts, amount, merchant_name,
         row_number() OVER (PARTITION BY product_id ORDER BY ts, transaction_id) rn_t
  FROM tx WHERE merchant_name IS NOT NULL""")

METRICS = """WITH s AS (SELECT product_id, merchant_name, ts, amount,
        lag(ts) OVER w pts, lag(amount) OVER w pamt, lag(ts, 2) OVER w ppts
      FROM {tab} WINDOW w AS (PARTITION BY product_id, merchant_name ORDER BY ts)),
  g AS (SELECT merchant_name, date_diff('day', pts, ts) gap, date_diff('day', ppts, pts) gap_prev, amount, pamt FROM s WHERE pts IS NOT NULL)
  SELECT merchant_name, count(*) n,
    sum((gap BETWEEN 27 AND 33)::INT) k27_33,
    sum((abs(amount/pamt-1)<0.05)::INT) k_amt5_strict,
    sum((abs(amount/pamt-1)<=0.05)::INT) k_amt5,
    sum((gap BETWEEN 27 AND 33 AND gap_prev BETWEEN 27 AND 33)::INT) k_two_monthly,
    sum((gap_prev IS NOT NULL)::INT) n_with_prev,
    sum(corr_x) FILTER (WHERE false) dummy
  FROM (SELECT *, NULL::DOUBLE corr_x FROM g) GROUP BY 1"""

obs = q(METRICS.format(tab="base"))
obs["src"] = "obs"
res = [obs]
SEEDS = [f"s{i}" for i in range(8)]
for sd in SEEDS:
    con.execute(f"""CREATE OR REPLACE TEMP TABLE perm AS
      WITH r AS (SELECT product_id, merchant_name,
                  row_number() OVER (PARTITION BY product_id ORDER BY hash(transaction_id || '{sd}')) rn_r FROM base)
      SELECT a.product_id, a.ts, a.amount, r.merchant_name
      FROM base a JOIN r ON a.product_id=r.product_id AND a.rn_t=r.rn_r""")
    d = q(METRICS.format(tab="perm"))
    d["src"] = sd
    res.append(d)
    con.execute("DROP TABLE perm")
allr = pd.concat(res)

tot = allr.groupby("src")[["n", "k27_33", "k_amt5_strict", "k_amt5", "k_two_monthly", "n_with_prev"]].sum()
tot["p27_33"] = tot.k27_33 / tot.n
tot["p_amt5_strict"] = tot.k_amt5_strict / tot.n
tot["p_amt5"] = tot.k_amt5 / tot.n
tot["p_two_monthly"] = tot.k_two_monthly / tot.n_with_prev
print("== Totales: observado vs 8 permutaciones dentro de producto ==")
print(tot.round(5).to_string())
nul = tot.drop("obs")
for c in ["p27_33", "p_amt5", "p_two_monthly", "k_two_monthly"]:
    o = tot.loc["obs", c]; m = nul[c].mean(); s = nul[c].std(ddof=1)
    print(f"{c}: obs={o:.5f} nulo={m:.5f}±{s:.5f}  razón={o/m:.3f}  z={(o-m)/s:.2f}")

print("\n== Por comercio: p27_33 observado vs media del nulo (8 permutaciones) ==")
pm = allr[allr.src != "obs"].groupby("merchant_name")[["n", "k27_33", "k_amt5"]].sum()
pm["p27_33_null"] = pm.k27_33 / pm.n
pm["p_amt5_null"] = pm.k_amt5 / pm.n
o = obs.set_index("merchant_name")
out = pd.DataFrame({"n": o.n, "p27_33": o.k27_33 / o.n, "p27_33_null": pm.p27_33_null,
                    "p_amt5_strict": o.k_amt5_strict / o.n, "p_amt5": o.k_amt5 / o.n, "p_amt5_null": pm.p_amt5_null})
out["ratio27_33"] = out.p27_33 / out.p27_33_null
out["z27_33"] = (out.p27_33 - out.p27_33_null) / np.sqrt(out.p27_33_null * (1 - out.p27_33_null) / out.n)
out["z_amt5"] = (out.p_amt5 - out.p_amt5_null) / np.sqrt(out.p_amt5_null * (1 - out.p_amt5_null) / out.n)
print(out.sort_values("z27_33", ascending=False).round(4).to_string())
print("rango p27_33: %.4f–%.4f ; rango p_amt5 estricto: %.4f–%.4f ; |z|>3.0 (Bonferroni 24): 27_33=%d amt5=%d" % (
    out.p27_33.min(), out.p27_33.max(), out.p_amt5_strict.min(), out.p_amt5_strict.max(),
    int((out.z27_33.abs() > 3.0).sum()), int((out.z_amt5.abs() > 3.0).sum())))

print("\n== ¿El monto depende del comercio? R² de log(monto) ~ comercio, dentro de cada moneda ==")
r2 = q("""WITH b AS (SELECT currency, merchant_name, ln(amount) la FROM tx WHERE merchant_name IS NOT NULL AND amount>0),
  g AS (SELECT currency, merchant_name, count(*) n, avg(la) m FROM b GROUP BY 1,2),
  c AS (SELECT currency, avg(la) mc, var_pop(la) vc, count(*) nc FROM b GROUP BY 1)
  SELECT c.currency, c.nc n, sum(g.n*(g.m-c.mc)^2)/(c.vc*c.nc) r2_between, min(exp(g.m)) min_geo_mean, max(exp(g.m)) max_geo_mean
  FROM g JOIN c USING (currency) GROUP BY c.currency, c.nc, c.vc""")
print(r2.round(5).to_string(index=False))
