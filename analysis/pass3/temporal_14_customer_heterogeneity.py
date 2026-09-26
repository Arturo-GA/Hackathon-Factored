"""H18: ¿hay 'huella temporal' por cliente? Dispersión entre clientes de: proporción fin de semana, proporción nocturna (hora local 0-6),
tasa de rechazo, fraude — frente a la varianza binomial esperada (razón ~1 => homogéneo, sin personalización posible).
H19: agrupamiento temporal de fraude/rechazos en el mismo producto; comportamiento tras un fraude."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
c = con.execute("""SELECT customer_id, count(*) n,
  sum((dayofweek(process_date) IN (0,6))::INT) wk, sum((hour(ts - INTERVAL 6 HOUR) < 6)::INT) night,
  sum((status='Declined')::INT) decl, sum(fraud::INT) fr, sum((fscore>=50)::INT) fs50, sum((channel IN ('App','Web'))::INT) dig
  FROM tx GROUP BY 1""").fetchdf()
print("clientes", len(c))
for k in ['wk', 'night', 'decl', 'fr', 'fs50', 'dig']:
    p = c[k].sum()/c.n.sum()
    x = c[c.n >= 10]
    obs_var = ((x[k] - x.n*p)**2).mean(); exp_var = (x.n*p*(1-p)).mean()
    print(f"{k}: p={p:.4f}  var_obs/var_binomial={obs_var/exp_var:.3f}  (n clientes {len(x)})")
# mismo por producto (el canal y tipo dependen del producto)
pp = con.execute("""SELECT product_id, count(*) n, sum((status='Declined')::INT) decl, sum(fraud::INT) fr, sum((dayofweek(process_date) IN (0,6))::INT) wk
  FROM tx GROUP BY 1""").fetchdf()
for k in ['decl', 'fr', 'wk']:
    p = pp[k].sum()/pp.n.sum(); x = pp[pp.n >= 5]
    print(f"producto {k}: var_obs/var_binomial={((x[k]-x.n*p)**2).mean()/(x.n*p*(1-p)).mean():.3f}")
# fraude: ¿clientes con >=2 fraudes más de lo esperado? distribución
print("fraudes por cliente:", c.fr.value_counts().sort_index().to_dict())
lam = c.n * c.fr.sum()/c.n.sum()
from scipy.stats import poisson
exp = {k: float(poisson.pmf(k, lam).sum()) for k in range(4)}
print("esperado Poisson:", {k: round(v, 1) for k, v in exp.items()})
# tras un fraude: siguiente tx del mismo producto
con.execute("""CREATE TEMP TABLE sq AS SELECT product_id, ts, fraud, status, fscore,
  lead(ts) OVER w nts, lead(status) OVER w nstatus, lead(fraud) OVER w nfraud, lag(ts) OVER w pts
  FROM tx WHERE product_id IN (SELECT DISTINCT product_id FROM tx WHERE fraud) WINDOW w AS (PARTITION BY product_id ORDER BY ts)""")
print(con.execute("""SELECT fraud, count(*) n, avg((nts IS NOT NULL)::INT) has_next, median(date_diff('hour', ts, nts))/24.0 med_days_next,
   avg((nstatus='Declined')::INT) next_decl, avg(nfraud::INT) next_fraud, avg((date_diff('hour', pts, ts) < 24)::INT) prev_lt24h
   FROM sq GROUP BY 1""").fetchdf().round(4).to_string(index=False))
