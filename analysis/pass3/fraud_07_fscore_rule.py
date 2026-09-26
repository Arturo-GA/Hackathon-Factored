"""Regla fraud_score: legítimas ~U(0,30], fraude ~U(0,100). Umbral óptimo, KS de uniformidad y posterior por tramo."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from scipy.stats import kstest
from fraud_00_common import connect, q
pd.set_option('display.width',200)
con = connect()
print(q(con,"""SELECT max(fscore) FILTER (WHERE NOT fraud) max_leg, count(*) FILTER (WHERE NOT fraud AND fscore=30) leg_eq30,
  min(fscore) FILTER (WHERE fraud AND fscore>30) min_fr_gt30, count(*) FILTER (WHERE fraud AND fscore>30) fr_gt30,
  count(*) FILTER (WHERE NOT fraud AND fscore>30) leg_gt30, count(*) FILTER (WHERE fraud) fr, count(*) FILTER (WHERE fraud AND fscore IS NOT NULL) fr_scored FROM tx"""))
for thr in [30,40,50]:
    d = q(con, f"SELECT count(*) FILTER (WHERE fscore>{thr} AND fraud) tp, count(*) FILTER (WHERE fscore>{thr}) pp, count(*) FILTER (WHERE fraud) p FROM tx")
    print(f"umbral >{thr}: precision {d.tp[0]/d.pp[0]:.4f}  recall {d.tp[0]/d.p[0]:.4f} (tp={d.tp[0]}, pp={d.pp[0]}, p={d.p[0]})")
# tramos -> posterior
d = q(con,"""SELECT CASE WHEN fscore IS NULL THEN 'nulo' WHEN fscore<=30 THEN '0-30' ELSE '>30' END tramo, count(*) n, sum(fraud::int) f FROM tx GROUP BY 1""")
d['p_fraude_pct']=100*d.f/d.n; print(d)
lo = d.set_index('tramo')
print('RR nulo vs 0-30:', (lo.loc['nulo','f']/lo.loc['nulo','n'])/(lo.loc['0-30','f']/lo.loc['0-30','n']))
# KS uniformidad
leg = q(con,"SELECT fscore FROM tx WHERE NOT fraud AND fscore IS NOT NULL USING SAMPLE 200000 ROWS").fscore.values
fr = q(con,"SELECT fscore FROM tx WHERE fraud AND fscore IS NOT NULL").fscore.values
print('KS legit vs U(0,30):', kstest(leg, 'uniform', args=(0,30)))
print('KS fraude vs U(0,100):', kstest(fr, 'uniform', args=(0,100)))
# fraude con score>30 vs <=30: ¿difieren en algo? (status, ttype, canal)
for c in ['status','ttype','channel','currency']:
    d = q(con, f"SELECT {c} v, count(*) FILTER (WHERE fscore>30) hi, count(*) FILTER (WHERE fscore<=30) lo, count(*) FILTER (WHERE fscore IS NULL) nul FROM tx WHERE fraud GROUP BY 1 ORDER BY 1")
    print(d.to_string(index=False))
# ¿el banco rechaza el fraude? tasa de Declined en fraude alto vs legítimo
print(q(con,"""SELECT CASE WHEN NOT fraud THEN 'legit' WHEN fscore>30 THEN 'fraude_hi' ELSE 'fraude_lo_nulo' END g, count(*) n,
 round(100*avg((status='Declined')::int),2) pct_declined, round(100*avg((status='Approved')::int),2) pct_approved FROM tx GROUP BY 1"""))
