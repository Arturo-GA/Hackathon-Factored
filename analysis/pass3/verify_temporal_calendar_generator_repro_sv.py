"""Complemento: relación diaria sv vs cc (residuos corr=1.000)."""
import duckdb, pandas as pd, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
d = con.execute("""WITH a AS (SELECT process_date d, count(*) ncc FROM cc GROUP BY 1),
 b AS (SELECT process_date d, count(*) nsv FROM sv GROUP BY 1)
 SELECT a.d, ncc, nsv FROM a JOIN b USING(d) ORDER BY 1""").fetchdf()
d['ratio'] = d.nsv / d.ncc
print(d.ratio.describe().round(4).to_string())
print("corr ncc-nsv:", round(np.corrcoef(d.ncc, d.nsv)[0,1], 4))
print(d.head(8).to_string(index=False))
# ¿sv.process_date = cc.process_date de su interacción?
print(con.execute("""SELECT count(*) n, avg(CASE WHEN s.process_date = c.process_date THEN 1 ELSE 0 END) same_pd,
  avg(date_diff('day', c.process_date, s.process_date)) mean_lag, count(c.interaction_id) AS n_matched
  FROM sv s LEFT JOIN cc c USING(interaction_id)""").fetchdf().to_string(index=False))
print(con.execute("SELECT count(*) n_sv, count(DISTINCT interaction_id) di, (SELECT count(*) FROM cc) n_cc FROM sv").fetchdf().to_string(index=False))
# si es submuestreo binomial, sd esperada del ratio
p = d.nsv.sum() / d.ncc.sum(); sd_bin = np.sqrt(p*(1-p)/d.ncc).mean()
print(f"p={p:.4f} sd ratio observada={d.ratio.std():.4f} sd binomial esperada={sd_bin:.4f}")
for f in [np.round, np.floor, np.ceil]:
    print(f.__name__, "nsv == f(0.31*ncc):", round(float((d.nsv == f(0.31*d.ncc)).mean()), 4), " |diff|<=1:", round(float((abs(d.nsv - 0.31*d.ncc) <= 1).mean()), 4))
