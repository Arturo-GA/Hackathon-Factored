"""Reclamos 'Cargo no reconocido': ¿el monto reclamado coincide con alguna tx (fraude) del cliente? ¿clientes con fraude reclaman más?
Transcripts/intents de fraude y mentioned_products."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30); pd.set_option('display.max_colwidth',120)
con = connect()
print(q(con,"SELECT subcategory, count(*) n, count(claimed) n_claimed, median(claimed) med, min(claimed) mn, max(claimed) mx FROM cp GROUP BY 1"))
# coincidencia exacta de monto (±0.01) con alguna tx del cliente en los 180 días previos
d = q(con,"""SELECT c.subcategory, count(DISTINCT c.complaint_id) n,
  count(DISTINCT c.complaint_id) FILTER (WHERE abs(t.amount-c.claimed)<0.01) match_any,
  count(DISTINCT c.complaint_id) FILTER (WHERE abs(t.amount-c.claimed)<0.01 AND t.fraud) match_fraud,
  count(DISTINCT c.complaint_id) FILTER (WHERE t.fraud) has_fraud_180d
 FROM cp c LEFT JOIN tx t ON t.customer_id=c.customer_id AND t.ts BETWEEN c.ts - INTERVAL 180 DAY AND c.ts
 WHERE c.claimed IS NOT NULL GROUP BY 1""")
print(d)
# ¿clientes con fraude tienen más reclamos Cargo no reconocido (cualquier momento)? tasa por cliente
d = q(con,"""WITH f AS (SELECT customer_id, max(fraud::int) hasf, count(*) ntx FROM tx GROUP BY 1),
 r AS (SELECT customer_id, count(*) FILTER (WHERE subcategory='Cargo no reconocido') cnr, count(*) nall FROM cp GROUP BY 1)
 SELECT hasf, count(*) n, avg(coalesce(cnr,0)) cnr_per_c, avg((coalesce(cnr,0)>0)::int) pct_any_cnr, avg(coalesce(nall,0)) all_per_c, avg(ntx) ntx FROM f LEFT JOIN r USING(customer_id) GROUP BY 1""")
print(d)
# intents / keywords
print(q(con,"SELECT detected_intents, count(*) n FROM tr GROUP BY 1 ORDER BY n DESC LIMIT 15"))
print(q(con,"SELECT count(*) n, count(*) FILTER (WHERE lower(full_text) LIKE '%fraud%') fr, count(*) FILTER (WHERE lower(full_text) LIKE '%no reconoz%' OR lower(full_text) LIKE '%bloque%') blq FROM tr"))
