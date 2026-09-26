"""¿Qué pasa DESPUÉS de una tx fraudulenta? Diseño antes/después vs control (tx legítimas aleatorias ~1%).
Ventanas 1/3/30/90 días: tx del cliente/producto, rechazos, eventos digitales (Error, Login, ip_country≠país cliente),
reclamos 'Cargo no reconocido', contactos call center. Diferencia-en-diferencias (después - antes)."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',40)
con = connect()
con.execute("""CREATE TEMP TABLE a AS
SELECT t.transaction_id aid, t.customer_id, t.product_id, t.ts, t.fraud, (t.fscore>30) hi, c.country ccountry
FROM tx t JOIN cu c USING(customer_id)
WHERE t.fraud OR (hash(t.transaction_id) % 100 = 0 AND NOT t.fraud)""")
print(q(con,"SELECT fraud, count(*) FROM a GROUP BY 1"))
W=[1,3,30,90]
def win(tbl, tscol, key, cond, name):
    cols = []
    for w in W:
        cols.append(f"count(*) FILTER (WHERE x.{tscol} > a.ts AND x.{tscol} <= a.ts + INTERVAL {w} DAY AND {cond}) aft{w}")
        cols.append(f"count(*) FILTER (WHERE x.{tscol} < a.ts AND x.{tscol} >= a.ts - INTERVAL {w} DAY AND {cond}) bef{w}")
    sql = f"""SELECT a.aid, a.fraud, {', '.join(cols)} FROM a LEFT JOIN {tbl} x ON x.{key}=a.{key}
      AND x.{tscol} BETWEEN a.ts - INTERVAL 90 DAY AND a.ts + INTERVAL 90 DAY GROUP BY a.aid, a.fraud"""
    d = q(con, sql)
    g = d.groupby('fraud').mean(numeric_only=True)
    res = []
    for w in W:
        af, bf = g.loc[True, f'aft{w}'], g.loc[True, f'bef{w}']
        ac, bc = g.loc[False, f'aft{w}'], g.loc[False, f'bef{w}']
        res.append(dict(metric=name, w=w, fraud_after=af, fraud_before=bf, ctrl_after=ac, ctrl_before=bc,
                        rr_after=af/ac if ac else np.nan, did=(af-bf)-(ac-bc)))
    return pd.DataFrame(res)
out = []
out.append(win('tx','ts','customer_id',"x.transaction_id<>a.aid",'tx cliente'))
out.append(win('tx','ts','product_id',"x.transaction_id<>a.aid",'tx mismo producto'))
out.append(win('tx','ts','customer_id',"x.status='Declined'",'tx rechazadas cliente'))
out.append(win('tx','ts','customer_id',"x.fraud AND x.transaction_id<>a.aid",'otro fraude cliente'))
out.append(win('tx','ts','customer_id',"x.status='Reversed'",'tx reversadas cliente'))
out.append(win('cp','ts','customer_id',"x.subcategory='Cargo no reconocido'",'reclamo cargo no reconocido'))
out.append(win('cp','ts','customer_id',"true",'reclamos'))
out.append(win('cc','ts','customer_id',"true",'contactos cc'))
out.append(win('cc','ts','customer_id',"x.cat='Transaccional'",'contactos transaccionales'))
out.append(win('de','ts','customer_id',"x.event_type='Error'",'eventos Error'))
out.append(win('de','ts','customer_id',"x.event_type='Login'",'eventos Login'))
out.append(win('de','ts','customer_id',"x.ip_country<>a.ccountry",'eventos ip≠país cliente'))
out.append(win('de','ts','customer_id',"true",'eventos digitales'))
out.append(win('sv','ts','customer_id',"true",'encuestas'))
r = pd.concat(out)
print(r.round(4).to_string(index=False))
r.to_csv('analysis/pass3/fraud_06_after.csv', index=False)
