"""Verificador escéptico: fraud_digital_sin_anomalia_geo (parte 5: lags a nivel sesión, product_id de eventos, país tx fraude vs IP)."""
import sys, time; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from scipy.stats import chisquare
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',40); pd.set_option('display.max_rows',100)
con = connect()
t=time.time()
con.execute("""CREATE TEMP TABLE a AS SELECT transaction_id aid, customer_id, product_id, ts, fraud, country, channel FROM tx
 WHERE channel IN ('App','Web') AND hash(transaction_id)%10=0 AND ts BETWEEN TIMESTAMP '2023-07-20' AND TIMESTAMP '2026-05-15'""")
con.execute("""CREATE TEMP TABLE ss AS SELECT session_id, max(customer_id) cid, min(ts) t0 FROM de WHERE customer_id IS NOT NULL GROUP BY 1""")
lag = q(con,"""SELECT floor(date_diff('second', a.ts, s.t0)/3600.0/6) h6, count(*) n FROM a JOIN ss s ON s.cid=a.customer_id
  AND s.t0 BETWEEN a.ts - INTERVAL 72 HOUR AND a.ts + INTERVAL 72 HOUR - INTERVAL 1 SECOND GROUP BY 1 ORDER BY 1""")
print('n tx', q(con,'SELECT count(*) n FROM a').n[0])
print('lags (bins de 6h, sesiones):'); print(lag.set_index('h6').n.to_dict())
print('chi2 uniformidad', chisquare(lag.n), 'ratio bin[-1,0] / media resto', round(lag[lag.h6.isin([-1,0])].n.mean()/lag[~lag.h6.isin([-1,0])].n.mean(),3))
print("== product_id en eventos digitales ==")
print(q(con,"""SELECT count(*) n, count(d.product_id) con_prod, count(p.product_id) prod_existe, count(*) FILTER (WHERE p.customer_id=d.customer_id) prod_del_mismo_cli
  FROM de d LEFT JOIN pr p ON p.product_id=d.product_id WHERE d.customer_id IS NOT NULL"""))
print(q(con,"SELECT product_id FROM de WHERE product_id IS NOT NULL USING SAMPLE 3 ROWS"))
print("== tx fraude fuera del país del cliente: ¿algún evento digital con IP de ese país? ==")
print(q(con,"""WITH f AS (SELECT t.transaction_id, t.customer_id, t.ts, t.country tctry, c.country cctry FROM tx t JOIN cu c USING(customer_id) WHERE t.fraud)
  SELECT count(*) n_fraude, count(*) FILTER (WHERE tctry<>cctry) fuera_pais,
   (SELECT count(*) FROM f JOIN de x ON x.customer_id=f.customer_id AND x.ts BETWEEN f.ts - INTERVAL 7 DAY AND f.ts + INTERVAL 7 DAY AND x.ip_country<>f.cctry) ev_ip_otro_pais_7d
  FROM f"""))
print(round(time.time()-t,1),'s')
