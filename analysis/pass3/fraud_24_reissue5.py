"""Perfil de las aperturas de OTROS productos tras fraude: días hasta la apertura, mismo tipo que el producto defraudado, canal de apertura. Intra-cliente."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',40)
con = connect()
con.execute("""CREATE TEMP TABLE fc AS SELECT DISTINCT customer_id FROM tx WHERE fraud""")
con.execute("""CREATE TEMP TABLE a AS SELECT t.transaction_id aid, t.customer_id, t.product_id pid, p.ptype aptype, t.ts, t.fraud FROM tx t JOIN pr p USING(product_id) JOIN fc ON fc.customer_id=t.customer_id""")
e = q(con, """SELECT a.fraud, date_diff('day', a.ts::date, x.opened) dd, (x.ptype=a.aptype) same_type, x.ptype, x.opening_channel, x.pstatus, count(*) n
  FROM a JOIN pr x ON x.customer_id=a.customer_id AND x.product_id<>a.pid AND x.opened > a.ts::date AND x.opened <= a.ts::date + 30 GROUP BY ALL""")
na = q(con, "SELECT fraud, count(*) n FROM a GROUP BY 1").set_index('fraud').n
def rate(df, by):
    t = df.groupby([by,'fraud']).n.sum().unstack('fraud').fillna(0)
    t['rF']=t[True]/na[True]*1e3; t['rL']=t[False]/na[False]*1e3; t['ratio']=t.rF/t.rL; t['exceso_F']=t[True]-t.rL*na[True]/1e3
    return t.round(3)
e['dbin']=pd.cut(e.dd,[0,3,7,14,21,30])
print(rate(e,'dbin')); print(rate(e,'same_type')); print(rate(e,'ptype')); print(rate(e,'opening_channel')); print(rate(e,'pstatus'))
