"""Verificador escéptico: fraud_digital_sin_anomalia_geo (parte 4: tx App/Web vs eventos digitales con ventanas placebo y lags)."""
import sys, time; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',40); pd.set_option('display.max_rows',100)
con = connect()
t=time.time()
print(q(con,"SELECT channel, count(*) n, count(*) FILTER (WHERE fraud) n_fraud FROM tx GROUP BY 1 ORDER BY 2 DESC"))
print(q(con,"SELECT min(ts), max(ts) FROM de"))
# muestra: todo fraude App/Web + 5% legítimas (hash), lejos de los bordes del periodo para las ventanas placebo
con.execute("""CREATE TEMP TABLE a AS SELECT transaction_id aid, customer_id, product_id, ts, fraud, channel, ttype, status FROM tx
 WHERE channel IN ('App','Web') AND (fraud OR hash(transaction_id)%20=0)
   AND ts BETWEEN TIMESTAMP '2023-07-20' AND TIMESTAMP '2026-05-15'""")
print(q(con,"SELECT fraud, count(*) n FROM a GROUP BY 1"))
# eventos del cliente en ventana real ±24h y placebo desplazado ±7d y ±30d (ventanas de 48h)
sql = """SELECT a.aid, a.fraud,
  count(x.event_id) FILTER (WHERE x.ts BETWEEN a.ts - INTERVAL 1 HOUR AND a.ts + INTERVAL 1 HOUR) e1h,
  count(x.event_id) FILTER (WHERE x.ts BETWEEN a.ts - INTERVAL 1 DAY AND a.ts + INTERVAL 1 DAY) e24,
  count(x.event_id) FILTER (WHERE x.ts BETWEEN a.ts - INTERVAL 1 DAY AND a.ts + INTERVAL 1 DAY AND x.product_id=a.product_id) e24_prod,
  count(x.event_id) FILTER (WHERE x.ts BETWEEN a.ts + INTERVAL 6 DAY AND a.ts + INTERVAL 8 DAY) p7a,
  count(x.event_id) FILTER (WHERE x.ts BETWEEN a.ts - INTERVAL 8 DAY AND a.ts - INTERVAL 6 DAY) p7b,
  count(x.event_id) FILTER (WHERE x.ts BETWEEN a.ts + INTERVAL 29 DAY AND a.ts + INTERVAL 31 DAY) p30a,
  count(x.event_id) FILTER (WHERE x.ts BETWEEN a.ts - INTERVAL 31 DAY AND a.ts - INTERVAL 29 DAY) p30b
 FROM a LEFT JOIN de x ON x.customer_id=a.customer_id AND x.ts BETWEEN a.ts - INTERVAL 31 DAY AND a.ts + INTERVAL 31 DAY
 GROUP BY 1,2"""
d = q(con, sql); print('join', round(time.time()-t,1),'s', len(d))
cols=['e1h','e24','e24_prod','p7a','p7b','p30a','p30b']
out = pd.DataFrame({c: d.groupby('fraud')[c].apply(lambda s:(s>0).mean()*100) for c in cols}).round(2)
out['n']=d.groupby('fraud').size(); print(out)
allr = {c: round((d[c]>0).mean()*100,2) for c in cols}; print('total %', allr)
# IC95 de la diferencia fraude vs legítima en e24 (Wilson aprox.)
for c in ['e24','e1h']:
    f=d[d.fraud]; l=d[~d.fraud]
    pf=(f[c]>0).mean(); pl=(l[c]>0).mean(); se=np.sqrt(pf*(1-pf)/len(f)+pl*(1-pl)/len(l))
    print(c,'fraude',round(pf*100,2),'legit',round(pl*100,2),'dif IC95',round((pf-pl-1.96*se)*100,2),round((pf-pl+1.96*se)*100,2))
# histograma de lags (horas) evento - tx dentro de ±72h, para descartar desfase horario
lag = q(con,"""SELECT floor(date_diff('second', a.ts, x.ts)/3600.0) h, count(*) n FROM a JOIN de x ON x.customer_id=a.customer_id
  AND x.ts BETWEEN a.ts - INTERVAL 72 HOUR AND a.ts + INTERVAL 72 HOUR GROUP BY 1 ORDER BY 1""")
print('lags: bins', len(lag), 'media', round(lag.n.mean(),1), 'sd', round(lag.n.std(),1), 'max', lag.n.max(), 'en h=', lag.loc[lag.n.idxmax(),'h'],
      'min', lag.n.min(), '| bins -1,0:', lag[lag.h.isin([-1,0])].n.tolist())
from scipy.stats import chisquare
print('chi2 uniformidad lags', chisquare(lag.n))
print(round(time.time()-t,1),'s')
