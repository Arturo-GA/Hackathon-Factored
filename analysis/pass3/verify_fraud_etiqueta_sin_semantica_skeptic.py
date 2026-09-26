"""Chequeos escépticos del hallazgo fraud_etiqueta_sin_semantica:
1) ¿Se puede saber la dirección (débito/crédito) de un Adjustment? (canal, comercio, efecto en saldo)
2) AUC held-out (split por cliente) de un modelo de tasas por celda ttype x status x channel -> ¿≈0.50?"""
import duckdb, numpy as np, pandas as pd
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
df = lambda s: con.execute(s).df()

print("== Canal y comercio en Deposit / Adjustment ==")
print(df("""SELECT ttype, channel, count(*) n, round(100*avg((merchant_name IS NOT NULL)::int),1) pct_merch,
  round(100*avg((mcat IS NOT NULL)::int),1) pct_mcat FROM tx WHERE ttype IN ('Deposit','Adjustment') GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False))
print()

# 2) AUC held-out por cliente
split = "(hash(customer_id) % 10) < 7"
cells = df(f"""SELECT ttype, status, channel, sum(fraud::int) f, count(*) n FROM tx WHERE {split} GROUP BY 1,2,3""")
F, N = cells.f.sum(), cells.n.sum(); prior = F / N; k = 200.0
cells['score'] = (cells.f + k * prior) / (cells.n + k)   # suavizado bayesiano
con.register('cells', cells[['ttype', 'status', 'channel', 'score']])
# test: todos los positivos + muestra de negativos (con customer_id para bootstrap agrupado)
pos = df(f"""SELECT t.customer_id, c.score, 1 y FROM tx t JOIN cells c USING(ttype,status,channel) WHERE NOT ({split}) AND t.fraud""")
neg = df(f"""SELECT t.customer_id, c.score, 0 y FROM (SELECT * FROM tx WHERE NOT ({split}) AND NOT fraud USING SAMPLE 250000 ROWS) t
            JOIN cells c USING(ttype,status,channel)""")
d = pd.concat([pos, neg], ignore_index=True)
from sklearn.metrics import roc_auc_score
auc = roc_auc_score(d.y, d.score)
rng = np.random.default_rng(7)
cust = d.customer_id.unique(); idx = d.groupby('customer_id').indices
boots = []
for _ in range(300):
    s = rng.choice(cust, size=len(cust), replace=True)
    ii = np.concatenate([idx[c] for c in s])
    yy = d.y.values[ii]
    if yy.min() == yy.max():
        continue
    boots.append(roc_auc_score(yy, d.score.values[ii]))
print(f"Celdas={len(cells)}  test positivos={len(pos)}  negativos muestreados={len(neg)}")
print(f"AUC held-out (ttype x status x channel) = {auc:.4f}  IC95 bootstrap por cliente = [{np.percentile(boots,2.5):.4f}, {np.percentile(boots,97.5):.4f}]")
