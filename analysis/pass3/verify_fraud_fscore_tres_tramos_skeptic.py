"""Verificador escéptico: fraud_score en tres tramos (>30 fraude seguro, nulo=tasa base, <=30 sin información)."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from scipy.stats import kstest, ks_2samp, chi2_contingency
from sklearn.metrics import roc_auc_score
from fraud_00_common import connect, q
pd.set_option('display.width',220); pd.set_option('display.max_columns',30)
con = connect()

print('== 1. Conteos base / máximos ==')
print(q(con,"""SELECT count(*) n, sum(fraud::int) fr, count(DISTINCT transaction_id) nid,
  max(fscore) FILTER (WHERE NOT fraud) max_leg, min(fscore) FILTER (WHERE fraud AND fscore>30) min_fr_gt30,
  count(*) FILTER (WHERE NOT fraud AND fscore>30) leg_gt30, count(*) FILTER (WHERE NOT fraud AND fscore=30) leg_eq30,
  count(*) FILTER (WHERE fraud AND fscore=30) fr_eq30,
  count(*) FILTER (WHERE fraud AND fscore IS NOT NULL) fr_scored, count(*) FILTER (WHERE fraud AND fscore>30) fr_gt30,
  count(*) FILTER (WHERE fscore<0 OR fscore>100) out_range,
  count(*) FILTER (WHERE fscore IS NOT NULL AND fscore<>round(fscore,2)) not2dec FROM tx""").T)

print('== 2. Estabilidad de la regla por estrato (max legit, fraude>30 por estrato) ==')
for c in ["strftime(ts,'%Y')", 'country', 'currency', 'status', 'ttype', 'channel']:
    d = q(con, f"""SELECT {c} v, count(*) n, max(fscore) FILTER (WHERE NOT fraud) max_leg,
      count(*) FILTER (WHERE NOT fraud AND fscore>30) leg_gt30, count(*) FILTER (WHERE fraud) fr,
      count(*) FILTER (WHERE fraud AND fscore>30) fr_gt30 FROM tx GROUP BY 1 ORDER BY 1""")
    print(c, '\n', d.to_string(index=False))

print('== 3. Umbrales ==')
for thr in [29.99, 30, 35, 40, 50]:
    d = q(con, f"SELECT count(*) FILTER (WHERE fscore>{thr} AND fraud) tp, count(*) FILTER (WHERE fscore>{thr}) pp, count(*) FILTER (WHERE fraud) p, count(*) FILTER (WHERE fraud AND fscore IS NOT NULL) ps FROM tx")
    print(f">{thr}: prec {d.tp[0]}/{d.pp[0]}={d.tp[0]/d.pp[0]:.4f}  recall_total {d.tp[0]/d.p[0]:.4f}  recall_scored {d.tp[0]/d.ps[0]:.4f}")
# >=50 como en YA SABEMOS
d = q(con, "SELECT count(*) FILTER (WHERE fscore>=50 AND fraud) tp, count(*) FILTER (WHERE fscore>=50) pp, count(*) FILTER (WHERE fraud) p, count(*) FILTER (WHERE fraud AND fscore IS NOT NULL) ps FROM tx")
print(f">=50: prec {d.tp[0]/d.pp[0]:.4f} recall_total {d.tp[0]/d.p[0]:.4f} recall_scored {d.tp[0]/d.ps[0]:.4f}")

print('== 4. Tramos y tasas ==')
d = q(con,"""SELECT CASE WHEN fscore IS NULL THEN 'nulo' WHEN fscore<=30 THEN '0-30' ELSE '>30' END tramo, count(*) n, sum(fraud::int) f FROM tx GROUP BY 1""")
d['pct']=100*d.f/d.n; print(d)
lo=d.set_index('tramo'); base = d.f.sum()/d.n.sum(); print('tasa base %', 100*base)
r1 = lo.loc['nulo','f']/lo.loc['nulo','n']; r0 = lo.loc['0-30','f']/lo.loc['0-30','n']
se = np.sqrt(1/lo.loc['nulo','f']-1/lo.loc['nulo','n']+1/lo.loc['0-30','f']-1/lo.loc['0-30','n'])
print(f'RR nulo/<=30 = {r1/r0:.3f} IC95 [{np.exp(np.log(r1/r0)-1.96*se):.3f}, {np.exp(np.log(r1/r0)+1.96*se):.3f}]')
# Esperado teórico si nulo MCAR y fraude U(0,100): tasa<=30 = base*0.3*? -> comprobar mezcla
print('Predicción mecánica: tasa nulo≈base; tasa <=30 ≈ base*(0.3 fraude en <=30)/(fracción de legit con score≈1) ->',
      100*base*0.3*(1)/(1), '% aprox')

print('== 5. ¿Dentro de [0,30] el score ordena? ==')
d = q(con,"""SELECT floor(least(fscore,29.999)) b, count(*) n, sum(fraud::int) f FROM tx WHERE fscore<=30 GROUP BY 1 ORDER BY 1""")
d['pm']=1e4*d.f/d.n; print(d.to_string(index=False))
chi = chi2_contingency(np.c_[d.f, d.n-d.f]); print('chi2 30 bins de 1 punto: chi2=%.1f p=%.3f' % (chi[0], chi[1]))
fr_lo = q(con,"SELECT fscore FROM tx WHERE fraud AND fscore<=30").fscore.values
leg_lo = q(con,"SELECT fscore FROM tx WHERE NOT fraud AND fscore<=30 USING SAMPLE 200000 ROWS").fscore.values
print('n fraude<=30', len(fr_lo), 'KS 2 muestras fraude<=30 vs legit<=30:', ks_2samp(fr_lo, leg_lo))
y = np.r_[np.ones(len(fr_lo)), np.zeros(len(leg_lo))]; s = np.r_[fr_lo, leg_lo]
auc = roc_auc_score(y, s); rng = np.random.default_rng(0); bs=[]
for _ in range(300):
    i1 = rng.integers(0,len(fr_lo),len(fr_lo)); i0 = rng.integers(0,len(leg_lo),len(leg_lo))
    bs.append(roc_auc_score(np.r_[np.ones(len(i1)),np.zeros(len(i0))], np.r_[fr_lo[i1], leg_lo[i0]]))
print(f'AUC fscore dentro de <=30: {auc:.3f} IC95 [{np.percentile(bs,2.5):.3f}, {np.percentile(bs,97.5):.3f}]')

print('== 6. Nulo MCAR ==')
print(q(con,"""SELECT fraud, count(*) n, round(100*avg((fscore IS NULL)::int),2) null_pct FROM tx GROUP BY 1"""))
for c in ['status','country','ttype']:
    print(q(con, f"SELECT {c} v, round(100*avg((fscore IS NULL)::int),2) null_pct, count(*) n FROM tx GROUP BY 1 ORDER BY 1").to_string(index=False))

print('== 7. Techo AUC teórico con 3 tramos (orden >30, nulo, <=30) ==')
d = q(con,"""SELECT CASE WHEN fscore IS NULL THEN 1 WHEN fscore<=30 THEN 0 ELSE 2 END t, fraud, count(*) n FROM tx GROUP BY 1,2""")
pv = d.pivot(index='t', columns='fraud', values='n').fillna(0)
F = pv[True]/pv[True].sum(); L = pv[False]/pv[False].sum()
auc3 = sum(F[i]*L[j] for i in F.index for j in L.index if i>j) + 0.5*sum(F[i]*L[i] for i in F.index)
print('AUC 3 tramos =', round(auc3,4)); print(pv)

print('== 8. ¿El fraude >30 es un subconjunto distinto (estado/tipo)? fraude hi vs lo ==')
print(q(con,"""SELECT CASE WHEN fscore>30 THEN 'hi' WHEN fscore IS NULL THEN 'nulo' ELSE 'lo' END g, count(*) n,
  round(100*avg((status='Declined')::int),1) decl, round(100*avg((status='Approved')::int),1) appr, round(avg(amount_usd),1) amt_usd
  FROM tx WHERE fraud GROUP BY 1 ORDER BY 1"""))
