"""Verificador escéptico (reintento) de 'temporal_poisson_no_velocity'. Parte 4: la explotación.
¿'hora/día/canal inusual para ESTE cliente' o la velocidad predicen fraude o rechazo? AUC con IC95 bootstrap por cliente.
Rasgos leave-one-out por cliente: proporción de las OTRAS tx del cliente en el mismo bloque 6h / hora / día de semana / canal;
segundos desde la tx previa del cliente; nº de tx del cliente en las 24 h previas. Además: umbral de fscore (>30 vs >=50).
"""
import duckdb, pandas as pd, numpy as np
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

print(q("""SELECT fraud, count(*) n, max(fscore) max_fs, sum((fscore>30)::INT) gt30, sum((fscore>=50)::INT) ge50,
           sum((fscore IS NULL)::INT) fs_null FROM tx GROUP BY 1""").to_string(index=False))

d = q("""WITH b AS (SELECT transaction_id, customer_id, ts, fraud, status, channel,
     count(*) OVER (PARTITION BY customer_id) n,
     count(*) OVER (PARTITION BY customer_id, hour(ts - INTERVAL 6 HOUR)//6) kb,
     count(*) OVER (PARTITION BY customer_id, hour(ts)) kh,
     count(*) OVER (PARTITION BY customer_id, dayofweek(process_date)) kd,
     count(*) OVER (PARTITION BY customer_id, channel) kc,
     count(*) OVER (PARTITION BY customer_id ORDER BY ts RANGE BETWEEN INTERVAL 1 DAY PRECEDING AND CURRENT ROW) - 1 n24,
     date_diff('second', lag(ts) OVER (PARTITION BY customer_id ORDER BY ts), ts) gap FROM tx)
  SELECT customer_id, fraud, (status='Declined') decl, (hash(transaction_id) % 15 = 0) rnd,
         (kb-1)::DOUBLE/(n-1) s_blk6h, (kh-1)::DOUBLE/(n-1) s_hora, (kd-1)::DOUBLE/(n-1) s_dow, (kc-1)::DOUBLE/(n-1) s_canal,
         coalesce(gap, 1e9) gap, n24
  FROM b WHERE n >= 5 AND (fraud OR hash(transaction_id) % 15 = 0)""")
print("filas", len(d), "fraudes", int(d.fraud.sum()), "clientes", d.customer_id.nunique())
rng = np.random.default_rng(11)
feats = {'s_blk6h': -1, 's_hora': -1, 's_dow': -1, 's_canal': -1, 'gap': -1, 'n24': 1}  # signo: 'inusual/rápido' => más riesgo

def auc_ci(df, y, B=200):
    cust = df.customer_id.astype('category').cat.codes.values
    ncust = cust.max() + 1
    res = {}
    for f, sg in feats.items():
        x = sg * df[f].values; yy = df[y].values.astype(int)
        a = roc_auc_score(yy, x)
        bs = []
        for _ in range(B):
            w = np.bincount(rng.integers(0, ncust, ncust), minlength=ncust)[cust]
            m = w > 0
            bs.append(roc_auc_score(yy[m], x[m], sample_weight=w[m]))
        res[f] = (round(a, 4), round(np.percentile(bs, 2.5), 4), round(np.percentile(bs, 97.5), 4))
    return res

print("AUC fraude (todos los fraudes + muestra aleatoria no-fraude):")
for k, v in auc_ci(d[d.fraud | d.rnd], 'fraud').items(): print(f"  {k}: AUC={v[0]} IC95=[{v[1]}, {v[2]}]")
print("AUC rechazo (muestra aleatoria):")
for k, v in auc_ci(d[d.rnd], 'decl').items(): print(f"  {k}: AUC={v[0]} IC95=[{v[1]}, {v[2]}]")
