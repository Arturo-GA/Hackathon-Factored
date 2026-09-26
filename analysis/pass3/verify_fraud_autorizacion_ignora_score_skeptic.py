"""Verificador escéptico: fraud_autorizacion_ignora_score.
¿status/code independientes de fraud y fscore? Potencia (IC de RR), unidades de Reversed, tasa mensual,
estratos (Simpson), código dentro de Declined, fscore en legítimas por estado, nulos de fscore por estado."""
import sys; sys.path.insert(0, 'analysis/pass3')
import numpy as np, pandas as pd
from scipy.stats import chi2_contingency
from fraud_00_common import connect, q
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = connect()

def rr_ci(a, n1, b, n0):
    """razón de tasas a/n1 vs b/n0 con IC95 log-normal"""
    if a == 0 or b == 0: return np.nan, np.nan, np.nan
    r = (a/n1)/(b/n0); se = np.sqrt(1/a - 1/n1 + 1/b - 1/n0)
    return r, np.exp(np.log(r)-1.96*se), np.exp(np.log(r)+1.96*se)

def cramer(ct):
    ct = np.asarray(ct, float); ct = ct[ct.sum(1) > 0][:, ct.sum(0) > 0]
    chi2, p, dof, _ = chi2_contingency(ct, correction=False); n = ct.sum()
    return chi2, p, np.sqrt(chi2/(n*(min(ct.shape)-1)))

print('== 1. Estado por grupo (conteos) + RR vs legítimas con IC95 ==')
d = q(con, """SELECT CASE WHEN NOT fraud THEN 'legit' WHEN fscore>30 THEN 'fraud_hi' ELSE 'fraud_lo_null' END g, status, count(*) n
  FROM tx GROUP BY 1,2""")
pv = d.pivot(index='g', columns='status', values='n').fillna(0).astype(int)
pv['N'] = pv.sum(1); pv.loc['fraud_all'] = pv.loc['fraud_hi'] + pv.loc['fraud_lo_null']
print(pv)
for s in ['Approved', 'Declined', 'Pending', 'Reversed']:
    for g in ['fraud_hi', 'fraud_lo_null', 'fraud_all']:
        r, lo, hi = rr_ci(pv.loc[g, s], pv.loc[g, 'N'], pv.loc['legit', s], pv.loc['legit', 'N'])
        print(f"  {s:9s} {g:13s}: {100*pv.loc[g,s]/pv.loc[g,'N']:6.3f}% vs legit {100*pv.loc['legit',s]/pv.loc['legit','N']:6.3f}%  RR={r:.3f} IC95[{lo:.3f},{hi:.3f}] (n={pv.loc[g,s]})")
print('status x fraud: chi2=%.2f p=%.3g V=%.5f' % cramer(pv.loc[['legit', 'fraud_all'], ['Approved', 'Declined', 'Pending', 'Reversed']].values))

print('\n== 2. Código por grupo + RR ==')
d = q(con, """SELECT CASE WHEN NOT fraud THEN 'legit' WHEN fscore>30 THEN 'fraud_hi' ELSE 'fraud_lo_null' END g, coalesce(code,'NULL') code, count(*) n
  FROM tx GROUP BY 1,2""")
pc = d.pivot(index='g', columns='code', values='n').fillna(0).astype(int)
pc['N'] = pc.sum(1); pc.loc['fraud_all'] = pc.loc['fraud_hi'] + pc.loc['fraud_lo_null']
print(pc)
for c in [x for x in pc.columns if x != 'N']:
    r, lo, hi = rr_ci(pc.loc['fraud_all', c], pc.loc['fraud_all', 'N'], pc.loc['legit', c], pc.loc['legit', 'N'])
    print(f"  code {c:5s}: fraude {100*pc.loc['fraud_all',c]/pc.loc['fraud_all','N']:6.3f}% vs legit {100*pc.loc['legit',c]/pc.loc['legit','N']:6.3f}%  RR={r:.3f} IC95[{lo:.3f},{hi:.3f}]")
codes = [x for x in pc.columns if x != 'N']
print('code x fraud: chi2=%.2f p=%.3g V=%.5f' % cramer(pc.loc[['legit', 'fraud_all'], codes].values))

print('\n== 3. status x code (todas) para entender la semántica del código ==')
d = q(con, "SELECT status, coalesce(code,'NULL') code, count(*) n FROM tx GROUP BY 1,2")
print(d.pivot(index='status', columns='code', values='n').fillna(0).astype(int))

print('\n== 4. Dentro de Declined: distribución de código fraude vs legit ==')
d = q(con, "SELECT fraud, coalesce(code,'NULL') code, count(*) n FROM tx WHERE status='Declined' GROUP BY 1,2")
pdd = d.pivot(index='fraud', columns='code', values='n').fillna(0).astype(int); print(pdd)
print('code x fraud | Declined: chi2=%.2f p=%.3g V=%.5f' % cramer(pdd.values))

print('\n== 5. Legítimas: fscore por estado (¿el score de las legítimas cambia con el estado?) ==')
print(q(con, """SELECT status, count(*) n, round(100*avg((fscore IS NULL)::int),3) pct_null, round(avg(fscore),4) avg_fs,
  round(quantile_cont(fscore,0.5),3) med, round(100*avg((fscore>20)::int) FILTER (WHERE fscore IS NOT NULL),3) pct_gt20
  FROM tx WHERE NOT fraud GROUP BY 1 ORDER BY 1""").to_string(index=False))
d = q(con, """SELECT status, CASE WHEN fscore IS NULL THEN 'nulo' ELSE (floor(least(fscore,29.999)/3))::VARCHAR END b, count(*) n
  FROM tx WHERE NOT fraud GROUP BY 1,2""")
print('status x (10 bins fscore + nulo) | legit: chi2=%.2f p=%.3g V=%.5f' % cramer(d.pivot(index='status', columns='b', values='n').fillna(0).values))
d = q(con, """SELECT coalesce(code,'NULL') code, CASE WHEN fscore IS NULL THEN 'nulo' ELSE (floor(least(fscore,29.999)/3))::VARCHAR END b, count(*) n
  FROM tx WHERE NOT fraud GROUP BY 1,2""")
print('code x (10 bins fscore + nulo) | legit: chi2=%.2f p=%.3g V=%.5f' % cramer(d.pivot(index='code', columns='b', values='n').fillna(0).values))
# AUC exacta via rangos (Mann-Whitney) de fscore para Declined vs no, solo legit con score
for tgt in ["status='Declined'", "status<>'Approved'", "status='Reversed'"]:
    a = q(con, f"""WITH s AS (SELECT fscore, ({tgt}) y FROM tx WHERE NOT fraud AND fscore IS NOT NULL),
      r AS (SELECT y, rank() OVER (ORDER BY fscore) rk FROM s)
      SELECT (sum(rk) FILTER (WHERE y) - count(*) FILTER (WHERE y)*(count(*) FILTER (WHERE y)+1)/2.0)
       / (count(*) FILTER (WHERE y)::DOUBLE * count(*) FILTER (WHERE NOT y)) auc, count(*) FILTER (WHERE y) npos FROM r""")
    n1 = a.npos[0]; auc = a.auc[0]; se = np.sqrt(auc*(1-auc)/n1)  # cota conservadora aprox
    print(f'  AUC fscore -> {tgt} (legit con score): {auc:.4f}  (±{1.96*se:.4f} aprox, npos={n1})')

print('\n== 6. Fraude: tasa de fraude por estado (‰) con RR vs Approved ==')
d = q(con, "SELECT status, count(*) n, sum(fraud::int) f, sum((fraud AND fscore>30)::int) fhi FROM tx GROUP BY 1 ORDER BY 1").set_index('status')
for s in d.index:
    r, lo, hi = rr_ci(d.loc[s, 'f'], d.loc[s, 'n'], d.loc['Approved', 'f'], d.loc['Approved', 'n'])
    print(f"  {s:9s} n={d.loc[s,'n']:>9,} fraude={d.loc[s,'f']:>5} ({1000*d.loc[s,'f']/d.loc[s,'n']:.3f}‰)  RR vs Approved={r:.3f} IC95[{lo:.3f},{hi:.3f}]  fraude_hi={d.loc[s,'fhi']}")

print('\n== 7. Tasa mensual de fraude_hi aprobado (verificar "66 al mes") ==')
print(q(con, """SELECT min(ts) mn, max(ts) mx, date_diff('day', min(ts)::DATE, max(ts)::DATE) dias,
  count(*) FILTER (WHERE fraud AND fscore>30 AND status='Approved') fhi_appr,
  count(DISTINCT date_trunc('month', ts)) FILTER (WHERE fraud AND fscore>30 AND status='Approved') meses_con
  FROM tx""").T)
m = q(con, """SELECT date_trunc('month', ts) m, count(*) n FROM tx WHERE fraud AND fscore>30 AND status='Approved' GROUP BY 1 ORDER BY 1""")
print('  por mes calendario: media=%.1f mediana=%.1f min=%d max=%d (meses=%d); primeros/últimos:' % (m.n.mean(), m.n.median(), m.n.min(), m.n.max(), len(m)))
print('  ', m.head(2).to_string(index=False, header=False).replace('\n', ' | '), ' ... ', m.tail(2).to_string(index=False, header=False).replace('\n', ' | '))
