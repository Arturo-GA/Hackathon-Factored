"""Verificador escéptico (ronda 2) fraud_digital_sin_anomalia_geo — parte B:
¿las tx App/Web tienen sesión digital asociada? Control por canal (POS/ATM/...), ventanas placebo, fraude vs legítima,
histograma de desfases (zona horaria) y actividad digital del cliente vs tasa de fraude."""
import sys, time; sys.path.insert(0, 'analysis/pass3')
import pandas as pd, numpy as np
from scipy.stats import chisquare
from fraud_00_common import connect, q
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 100)
con = connect()
t0 = time.time()
def T(m): print(f'\n[{time.time()-t0:.0f}s] == {m} ==', flush=True)

T('B0. rangos de fechas y canales')
print(q(con, "SELECT (SELECT min(ts) FROM de) de_min, (SELECT max(ts) FROM de) de_max, (SELECT min(ts) FROM tx) tx_min, (SELECT max(ts) FROM tx) tx_max"))
print(q(con, "SELECT channel, count(*) n, count(*) FILTER (WHERE fraud) fraude FROM tx GROUP BY 1 ORDER BY 2 DESC"))

# sesiones de clientes (solo eventos identificados)
con.execute("""CREATE TEMP TABLE ss AS SELECT session_id, max(customer_id) cid, min(ts) t0, max(ts) t1
  FROM de WHERE customer_id IS NOT NULL GROUP BY 1""")
# tx: muestra 10% por hash + todo el fraude, lejos de los bordes para que las ventanas placebo existan
con.execute("""CREATE TEMP TABLE a AS SELECT transaction_id aid, customer_id, ts, fraud, channel,
   CASE WHEN channel IN ('App','Web') THEN 'App/Web' ELSE 'Otros' END grp, hash(transaction_id)%10=0 mues
  FROM tx WHERE (hash(transaction_id)%10=0 OR fraud)
   AND ts BETWEEN TIMESTAMP '2023-07-20' AND TIMESTAMP '2026-05-15'""")
print(q(con, "SELECT grp, fraud, mues, count(*) n FROM a GROUP BY ALL ORDER BY ALL"))

T('B1. sesión del cliente que se solapa con ventana real vs placebo')
con.execute("""CREATE TEMP TABLE j AS SELECT a.aid, a.fraud, a.grp, a.channel, a.mues,
  coalesce(bool_or(s.t1 >= a.ts - INTERVAL 1 HOUR AND s.t0 <= a.ts + INTERVAL 1 HOUR), false) w1h,
  coalesce(bool_or(s.t1 >= a.ts - INTERVAL 1 DAY AND s.t0 <= a.ts + INTERVAL 1 DAY), false) w24,
  coalesce(bool_or(s.t1 >= a.ts + INTERVAL 6 DAY AND s.t0 <= a.ts + INTERVAL 8 DAY), false) p7a,
  coalesce(bool_or(s.t1 >= a.ts - INTERVAL 8 DAY AND s.t0 <= a.ts - INTERVAL 6 DAY), false) p7b,
  coalesce(bool_or(s.t1 >= a.ts + INTERVAL 29 DAY AND s.t0 <= a.ts + INTERVAL 31 DAY), false) p30a,
  coalesce(bool_or(s.t1 >= a.ts - INTERVAL 31 DAY AND s.t0 <= a.ts - INTERVAL 29 DAY), false) p30b,
  coalesce(bool_or(s.t1 >= a.ts - INTERVAL 1 DAY AND s.t0 <= a.ts), false) antes24
  FROM a LEFT JOIN ss s ON s.cid = a.customer_id AND s.t1 >= a.ts - INTERVAL 32 DAY AND s.t0 <= a.ts + INTERVAL 32 DAY
  GROUP BY ALL""")
cols = ['w1h', 'w24', 'antes24', 'p7a', 'p7b', 'p30a', 'p30b']
agg = ', '.join(f"round(100*avg({c}::INT),3) {c}" for c in cols)
print('-- muestra 10% (todas las tx, % con sesión) por grupo de canal y fraude')
print(q(con, f"SELECT grp, fraud, count(*) n, {agg} FROM j WHERE mues GROUP BY ALL ORDER BY ALL"))
print('-- por canal (muestra 10%)')
print(q(con, f"SELECT channel, count(*) n, {agg} FROM j WHERE mues GROUP BY ALL ORDER BY 1"))
print('-- todo el fraude vs legítimas de la muestra, solo App/Web')
d = q(con, "SELECT fraud, w1h, w24, p7a, p7b, p30a, p30b FROM j WHERE grp='App/Web' AND (fraud OR mues)")
for c in ['w24', 'w1h']:
    f = d[d.fraud][c]; l = d[~d.fraud][c]
    pf, pl = f.mean(), l.mean(); se = np.sqrt(pf*(1-pf)/len(f) + pl*(1-pl)/len(l))
    print(f'{c}: fraude {100*pf:.2f}% ({int(f.sum())}/{len(f)})  legit {100*pl:.2f}% ({int(l.sum())}/{len(l)})  '
          f'dif IC95 [{100*(pf-pl-1.96*se):.2f}, {100*(pf-pl+1.96*se):.2f}] pp')
m = q(con, "SELECT grp, avg(w24::INT) w24, (avg(p7a::INT)+avg(p7b::INT)+avg(p30a::INT)+avg(p30b::INT))/4 placebo FROM j WHERE mues GROUP BY 1")
m['ratio_real_placebo'] = (m.w24/m.placebo).round(3); print(m)
w = m.set_index('grp').w24; print('RR App/Web vs Otros (w24):', round(w['App/Web']/w['Otros'], 3))

T('B2. desfases sesión - tx (App/Web, ±72h, bins 3h): ¿pico en 0 u offset fijo (zona horaria)?')
lag = q(con, """SELECT floor(date_diff('second', a.ts, s.t0)/10800.0) b, count(*) n FROM a JOIN ss s ON s.cid=a.customer_id
   AND s.t0 >= a.ts - INTERVAL 72 HOUR AND s.t0 < a.ts + INTERVAL 72 HOUR WHERE a.grp='App/Web' AND a.mues GROUP BY 1 ORDER BY 1""")
v = lag.set_index('b').n
print('bins (3h):', v.to_dict())
print('chi2 uniformidad', chisquare(v.values), '| bins centrales -1,0 / media resto:',
      round(v.loc[[-1, 0]].mean() / v.drop([-1, 0]).mean(), 3), '| max/min', v.max(), v.min())

T('B3. actividad digital del cliente vs tasa de fraude por tx (cuantiles de sesiones)')
print(q(con, """WITH sc AS (SELECT cid, count(*) nses FROM ss GROUP BY 1),
  tc AS (SELECT customer_id cid, count(*) ntx, count(*) FILTER (WHERE fraud) nf FROM tx GROUP BY 1),
  z AS (SELECT tc.*, coalesce(sc.nses,0) nses FROM tc LEFT JOIN sc USING(cid))
  SELECT ntile q5, count(*) clientes, min(nses) ses_min, max(nses) ses_max, sum(ntx) tx, sum(nf) fraudes,
    round(1000.0*sum(nf)/sum(ntx),3) fraude_x_mil FROM (SELECT *, ntile(5) OVER (ORDER BY nses, hash(cid)) ntile FROM z) GROUP BY 1 ORDER BY 1"""))
print(f'[{time.time()-t0:.0f}s] fin')
