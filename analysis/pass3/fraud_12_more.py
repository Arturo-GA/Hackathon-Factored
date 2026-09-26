"""Más hipótesis: country_raw, distancia tx-sucursal, montos repetidos del cliente, nulos de fscore por canal/tipo, estado del producto tras fraude."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
con = connect()
b = q(con,"SELECT avg(fraud::int) FROM tx").iloc[0,0]
d = q(con,"SELECT country_raw, country, count(*) n, sum(fraud::int) f FROM tx GROUP BY ALL ORDER BY n DESC"); d['rr']=d.f/d.n/b; print(d)
# distancia tx - sucursal
d = q(con,"""SELECT t.fraud, count(*) n, median(111*sqrt(pow(t.lat-b.lat,2)+pow((t.lon-b.lon)*cos(radians(t.lat)),2))) med_km,
  avg((111*sqrt(pow(t.lat-b.lat,2)+pow((t.lon-b.lon)*cos(radians(t.lat)),2))>50)::int) pct_gt50km, avg((t.city=b.city)::int) same_city
  FROM tx t JOIN br b USING(branch_id) WHERE t.lat IS NOT NULL GROUP BY 1"""); print(d)
print(q(con,"SELECT channel, count(*) n, count(branch_id) n_branch, count(lat) n_geo, count(merchant_name) n_merch FROM tx GROUP BY 1"))
# montos repetidos en el mismo cliente
d = q(con,"""WITH x AS (SELECT fraud, count(*) OVER (PARTITION BY customer_id, amount) k FROM tx)
 SELECT k>1 dup_amt, count(*) n, sum(fraud::int) f FROM x GROUP BY 1"""); d['rr']=d.f/d.n/b; print(d)
# nulos de fscore por canal / tipo / estado
print(q(con,"SELECT channel, round(100*avg((fscore IS NULL)::int),2) pct_null FROM tx GROUP BY 1 ORDER BY 1").T)
print(q(con,"SELECT ttype, round(100*avg((fscore IS NULL)::int),2) pct_null FROM tx GROUP BY 1 ORDER BY 1").T)
# estado del producto tras fraude
print(q(con,"""SELECT p.pstatus, count(DISTINCT p.product_id) n_prod, count(DISTINCT p.product_id) FILTER (WHERE t.fraud) n_prod_fraude,
  count(t.transaction_id) n_tx FROM pr p LEFT JOIN tx t USING(product_id) GROUP BY 1"""))
# last_updated del producto vs fecha de fraude
print(q(con,"""SELECT count(*) n, avg((p.last_updated >= t.ts)::int) pct_upd_after, median(date_diff('day', t.ts, p.last_updated)) med_days
 FROM tx t JOIN pr p USING(product_id) WHERE t.fraud"""))
print(q(con,"""SELECT count(*) n, avg((p.last_updated >= t.ts)::int) pct_upd_after, median(date_diff('day', t.ts, p.last_updated)) med_days
 FROM (SELECT * FROM tx WHERE NOT fraud USING SAMPLE 50000 ROWS) t JOIN pr p USING(product_id)"""))
