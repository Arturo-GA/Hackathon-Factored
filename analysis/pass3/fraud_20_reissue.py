"""¿Reemisión de producto tras fraude? Aperturas de productos del cliente (mismo tipo) y actualizaciones de cliente/producto en ventanas antes/después, fraude vs control."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
con = connect()
con.execute("""CREATE TEMP TABLE a AS SELECT t.transaction_id aid, t.customer_id, t.ts, t.fraud, p.ptype FROM tx t JOIN pr p USING(product_id)
 WHERE t.fraud OR (hash(t.transaction_id)%100=0 AND NOT t.fraud)""")
cols=[]
for w in [30,90]:
    cols += [f"count(x.product_id) FILTER (WHERE x.opened > a.ts::date AND x.opened <= a.ts::date + {w}) open_aft{w}",
             f"count(x.product_id) FILTER (WHERE x.opened <= a.ts::date AND x.opened > a.ts::date - {w}) open_bef{w}",
             f"count(x.product_id) FILTER (WHERE x.ptype=a.ptype AND x.opened > a.ts::date AND x.opened <= a.ts::date + {w}) same_aft{w}",
             f"count(x.product_id) FILTER (WHERE x.ptype=a.ptype AND x.opened <= a.ts::date AND x.opened > a.ts::date - {w}) same_bef{w}",
             f"count(x.product_id) FILTER (WHERE x.pstatus IN ('Blocked','Suspended','Closed') AND x.last_updated > a.ts AND x.last_updated <= a.ts + INTERVAL {w} DAY) blk_upd_aft{w}"]
d = q(con, f"SELECT a.aid, a.fraud, {', '.join(cols)} FROM a LEFT JOIN pr x ON x.customer_id=a.customer_id GROUP BY 1,2")
g = d.drop(columns='aid').groupby('fraud').mean().T; g['rr']=g[True]/g[False]; print(g.round(4))
d = q(con, """SELECT a.fraud, avg((c.last_updated > a.ts AND c.last_updated <= a.ts + INTERVAL 30 DAY)::int) cu_upd30, avg((c.cstatus<>'Active')::int) not_active
 FROM a JOIN cu c USING(customer_id) GROUP BY 1"""); print(d)
