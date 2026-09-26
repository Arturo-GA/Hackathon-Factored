"""hunt_42: dentro de contactos Transaccionales, ¿el contexto transaccional reciente del cliente (rechazos, fraude, pendientes,
tx en los 7/30 dias previos) cambia la resolucion (FCR), el escalamiento o la duracion?
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_42_transacc_context.py
"""
import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
df = con.execute("""
WITH c AS (SELECT interaction_id, customer_id, ts, CAST(resolved AS INT) res, CAST(escalated AS INT) esc, dur FROM cc WHERE cat='Transaccional')
SELECT c.interaction_id, any_value(c.res) res, any_value(c.esc) esc, any_value(c.dur) dur,
  count(t.transaction_id) FILTER (WHERE t.ts >= c.ts - INTERVAL 7 DAY) n7,
  count(t.transaction_id) FILTER (WHERE t.status='Declined' AND t.ts >= c.ts - INTERVAL 7 DAY) dec7,
  count(t.transaction_id) FILTER (WHERE t.status='Declined') dec30,
  count(t.transaction_id) FILTER (WHERE t.status IN ('Pending','Reversed')) pr30,
  count(t.transaction_id) FILTER (WHERE t.fraud) fr30,
  count(t.transaction_id) FILTER (WHERE t.fscore >= 50) fs30,
  count(t.transaction_id) n30
FROM c LEFT JOIN tx t ON t.customer_id = c.customer_id AND t.ts BETWEEN c.ts - INTERVAL 30 DAY AND c.ts
GROUP BY c.interaction_id""").df()
print('contactos transaccionales:', len(df), ' FCR', round(df.res.mean(), 4))
for f in ['n7', 'dec7', 'dec30', 'pr30', 'fr30', 'fs30', 'n30']:
    has = df[f] > 0
    print(f"{f}: con>0 n={has.sum()} ({has.mean():.1%}) FCR={df.res[has].mean():.4f} vs {df.res[~has].mean():.4f}  esc={df.esc[has].mean():.4f} vs {df.esc[~has].mean():.4f}"
          f"  AUC(->no resuelto)={roc_auc_score(1-df.res, df[f]):.4f}")
