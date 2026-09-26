"""Hipótesis 'phishing': ¿envíos/clics de campaña en los días previos a un fraude? Fraude vs control (tx legítimas ~1%)."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
con = connect()
con.execute("""CREATE TEMP TABLE a AS SELECT transaction_id aid, customer_id, ts, fraud FROM tx WHERE fraud OR (hash(transaction_id)%100=0 AND NOT fraud)""")
cols=[]
for w in [3,7,30]:
    for nm,cond in [('send','true'),('open','x.opened'),('click','x.clicked'),('fail',"x.send_status<>'Delivered'"),('sms',"x.send_channel='SMS'")]:
        cols.append(f"count(x.send_id) FILTER (WHERE x.ts < a.ts AND x.ts >= a.ts - INTERVAL {w} DAY AND {cond}) {nm}_{w}d")
d = q(con, f"SELECT a.aid, a.fraud, {', '.join(cols)} FROM a LEFT JOIN cs x ON x.customer_id=a.customer_id AND x.ts BETWEEN a.ts - INTERVAL 30 DAY AND a.ts GROUP BY 1,2")
g = d.drop(columns='aid').groupby('fraud').mean().T
g['rr']=g[True]/g[False]; print(g.round(4))
anyc = d.assign(c=d.click_30d>0).groupby('fraud').c.agg(['mean','sum','count']); print(anyc)
print(q(con,"SELECT send_status, count(*) FROM cs GROUP BY 1"))
