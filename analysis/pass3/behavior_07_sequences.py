"""Secuencias: matriz de transición ttype(t-1)->ttype(t) en el producto y en el cliente vs marginal;
depósito->retiro; gaps; día del mes / semana por ttype."""
from behavior_common import connect, q
import numpy as np, pandas as pd
con = connect()
for part in ['product_id', 'customer_id']:
    m = q(con, f"""WITH s AS (SELECT ttype, lag(ttype) OVER (PARTITION BY {part} ORDER BY ts) prev FROM tx)
      SELECT prev, ttype, count(*) n FROM s WHERE prev IS NOT NULL GROUP BY 1,2""")
    pv = m.pivot(index='prev', columns='ttype', values='n').fillna(0)
    rowp = pv.div(pv.sum(axis=1), axis=0)
    # expected under independence within ptype handled for product partition via lift
    marg = pv.sum(axis=0)/pv.values.sum()
    print(f"== partición {part}: P(next|prev) ==\n", (rowp*100).round(1))
    print("lift vs marginal:\n", (rowp/marg).round(2))
# gap
print(q(con, """WITH s AS (SELECT ts, lag(ts) OVER (PARTITION BY product_id ORDER BY ts) p FROM tx)
  SELECT quantile_cont(epoch(ts-p)/86400,[0.01,0.1,0.25,0.5,0.75,0.9,0.99]) q, avg(epoch(ts-p)/86400) mean, stddev(epoch(ts-p)/86400) sd FROM s WHERE p IS NOT NULL"""))
# dia del mes por ttype (depositos nómina?)
dm = q(con, "SELECT ttype, day(ts) d, count(*) n FROM tx GROUP BY 1,2")
pv = dm.pivot(index='d', columns='ttype', values='n')
pv = pv.div(pv.sum(axis=0), axis=1)*100
print("día del mes %: min/max por ttype\n", pv.agg(['min','max']).round(2))
print(pv.loc[[1,14,15,16,28,29,30,31]].round(2))
dw = q(con, "SELECT ttype, dayofweek(ts) d, count(*) n FROM tx GROUP BY 1,2")
pv = dw.pivot(index='d', columns='ttype', values='n'); print((pv.div(pv.sum(axis=0), axis=1)*100).round(2))
hm = q(con, "SELECT month(ts) m, count(*) n FROM tx GROUP BY 1 ORDER BY 1"); print(hm.T)
ym = q(con, "SELECT date_trunc('month', ts) m, count(*) n FROM tx GROUP BY 1 ORDER BY 1"); print(ym.n.describe(), ym.head(3), ym.tail(3))
