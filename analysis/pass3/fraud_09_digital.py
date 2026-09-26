"""Eventos digitales: regla ip_country = país del cliente; variante 'Mexico' solo en anónimos; sesión digital alrededor de tx App/Web fraude vs legítima."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
con = connect()
print(q(con,"""SELECT (d.customer_id IS NULL) anon, d.ip_country, c.country ccountry, count(*) n FROM de d LEFT JOIN cu c USING(customer_id) GROUP BY ALL ORDER BY 1,2,3"""))
print(q(con,"""SELECT count(*) n, count(*) FILTER (WHERE d.ip_city=c.city) same_city, count(*) FILTER (WHERE d.ip_city IS NULL) null_city FROM de d JOIN cu c USING(customer_id)"""))
print(q(con,"""SELECT (customer_id IS NULL) anon, is_mobile, platform, count(*) n FROM de GROUP BY ALL ORDER BY 1,4 DESC LIMIT 20"""))
# eventos alrededor de tx App/Web: ¿hay evento digital del cliente en ±1h / ±24h? fraude vs control
con.execute("""CREATE TEMP TABLE a AS SELECT transaction_id aid, customer_id, ts, fraud, channel FROM tx
 WHERE channel IN ('App','Web') AND (fraud OR hash(transaction_id)%50=0)""")
d = q(con,"""SELECT a.aid, a.fraud, a.channel,
  count(x.event_id) FILTER (WHERE abs(date_diff('second',x.ts,a.ts))<=3600) e1h,
  count(x.event_id) FILTER (WHERE abs(date_diff('second',x.ts,a.ts))<=86400) e24h,
  count(x.event_id) FILTER (WHERE abs(date_diff('second',x.ts,a.ts))<=3600 AND x.event_type='Purchase') p1h,
  count(x.event_id) FILTER (WHERE abs(date_diff('second',x.ts,a.ts))<=86400 AND x.event_type='Error') err24
 FROM a LEFT JOIN de x ON x.customer_id=a.customer_id AND x.ts BETWEEN a.ts - INTERVAL 1 DAY AND a.ts + INTERVAL 1 DAY GROUP BY 1,2,3""")
g = d.assign(any1h=d.e1h>0, any24=d.e24h>0, anyp=d.p1h>0, anyerr=d.err24>0).groupby('fraud')[['any1h','any24','anyp','anyerr','e24h']].agg(['mean','count'])
print(g)
