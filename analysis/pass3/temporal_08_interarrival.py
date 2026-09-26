"""H13: proceso de llegada por cliente/producto. ¿Poisson homogéneo? tx por producto (varianza/media),
tiempos entre tx del mismo cliente y producto (CV, cuantiles vs exponencial), ráfagas (<1 min, <1 h), mismos segundos."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
print("tx por producto:")
print(con.execute("""WITH a AS (SELECT product_id, count(*) n FROM tx GROUP BY 1)
  SELECT count(*) prods, avg(n) mean, var_samp(n) var, var_samp(n)/avg(n) disp, min(n), max(n),
  quantile_cont(n,[0.01,0.1,0.5,0.9,0.99]) q FROM a""").fetchdf().T)
print(con.execute("""WITH a AS (SELECT product_id, count(*) n FROM tx GROUP BY 1)
  SELECT p.ptype, count(*) prods, avg(n) mean, var_samp(n)/avg(n) disp, min(n) mn, max(n) mx FROM a JOIN pr p USING(product_id) GROUP BY 1 ORDER BY 1""").fetchdf().to_string(index=False))
print("tx por cliente:")
print(con.execute("""WITH a AS (SELECT customer_id, count(*) n, count(DISTINCT product_id) np FROM tx GROUP BY 1)
  SELECT count(*) custs, avg(n) mean, var_samp(n)/avg(n) disp, corr(n, np) corr_n_nprod, avg(n/np) tx_per_prod FROM a""").fetchdf().T)
# muestra de 15% de productos para intervalos
con.execute("""CREATE TEMP TABLE s AS SELECT product_id, customer_id, ts, ttype, status, amount, channel FROM tx
  WHERE hash(product_id) % 7 = 0""")
print("filas muestra", con.execute("SELECT count(*) FROM s").fetchone())
con.execute("""CREATE TEMP TABLE g AS SELECT product_id, ts, ttype, status, channel,
   date_diff('second', lag(ts) OVER (PARTITION BY product_id ORDER BY ts), ts) gap,
   count(*) OVER (PARTITION BY product_id) n, lag(ttype) OVER (PARTITION BY product_id ORDER BY ts) prev_t,
   lag(status) OVER (PARTITION BY product_id ORDER BY ts) prev_s FROM s""")
print(con.execute("""SELECT count(gap) n_gaps, avg(gap)/86400 mean_days, stddev(gap)/avg(gap) cv,
  quantile_cont(gap/86400.0,[0.01,0.1,0.25,0.5,0.75,0.9,0.99]) q_days,
  avg((gap=0)::INT) same_second, avg((gap<60)::INT) lt1min, avg((gap<3600)::INT) lt1h, avg((gap<86400)::INT) lt1d FROM g""").fetchdf().T)
# comparación con exponencial: gap normalizado por la tasa del producto (n/1096 días)
g = con.execute("""SELECT gap/86400.0 * (n/1096.0) z FROM g WHERE gap IS NOT NULL USING SAMPLE 200000 ROWS""").fetchdf().z.values
print("gap normalizado: media", g.mean().round(3), "cv", (g.std()/g.mean()).round(3))
for p in [0.1, 0.25, 0.5, 0.75, 0.9, 0.99]:
    print(f"  q{p}: obs={np.quantile(g, p):.3f}  exp(1)={-np.log(1-p):.3f}  (uniforme-orden n puntos ~ exp)")
# conteos por producto-mes: índice de dispersión (Poisson => 1)
print(con.execute("""WITH m AS (SELECT product_id, date_trunc('month', ts) mo, count(*) k FROM s GROUP BY ALL),
  p AS (SELECT product_id, count(*) n FROM s GROUP BY 1),
  grid AS (SELECT p.product_id, p.n, mo.mo FROM p CROSS JOIN (SELECT DISTINCT date_trunc('month', ts) mo FROM s WHERE ts >= '2023-07-01' AND ts < '2026-06-01') mo),
  j AS (SELECT grid.product_id, grid.n, coalesce(m.k,0) k FROM grid LEFT JOIN m USING(product_id, mo))
  SELECT avg(k) mean_k, var_samp(k) var_k, var_samp(k)/avg(k) disp FROM j""").fetchdf())
# ¿el tipo/estado de la tx depende del anterior del mismo producto? (cadena de Markov)
t = con.execute("SELECT prev_s, status, count(*) n FROM g WHERE prev_s IS NOT NULL GROUP BY ALL").fetchdf().pivot(index='prev_s', columns='status', values='n')
print((t.div(t.sum(1), axis=0)).round(4))
t = con.execute("SELECT prev_t, ttype, count(*) n FROM g WHERE prev_t IS NOT NULL GROUP BY ALL").fetchdf().pivot(index='prev_t', columns='ttype', values='n')
print((t.div(t.sum(1), axis=0)).round(3))
# ¿rechazo más probable si gap corto?
print(con.execute("""SELECT CASE WHEN gap<3600 THEN 'a<1h' WHEN gap<86400 THEN 'b<1d' WHEN gap<7*86400 THEN 'c<7d' WHEN gap<30*86400 THEN 'd<30d' ELSE 'e>=30d' END b,
   count(*) n, avg((status='Declined')::INT) decl, avg((status='Reversed')::INT) rev FROM g WHERE gap IS NOT NULL GROUP BY 1 ORDER BY 1""").fetchdf().to_string(index=False))
