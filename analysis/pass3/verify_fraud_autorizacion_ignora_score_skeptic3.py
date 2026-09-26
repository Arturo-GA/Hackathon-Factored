"""Verificador escéptico (parte 3): fraud_autorizacion_ignora_score.
(e) Test global 17 celdas (status x code) fraude vs legit + p familiar por simulación multinomial (max |z|).
(f) Población completa: estado de la tx SIGUIENTE del mismo producto / cliente según la tx previa fue fraude (lag).
(g) Dentro del fraude con score: AUC de fscore para Declined / no-Approved con IC bootstrap."""
import sys; sys.path.insert(0, 'analysis/pass3')
import numpy as np, pandas as pd
from scipy.stats import chi2_contingency, chi2 as chi2d
from sklearn.metrics import roc_auc_score
from fraud_00_common import connect, q
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = connect()

def rr_ci(a, n1, b, n0):
    r = (a/n1)/(b/n0); se = np.sqrt(1/a - 1/n1 + 1/b - 1/n0)
    return r, np.exp(np.log(r)-1.96*se), np.exp(np.log(r)+1.96*se)

print('== (e) 17 celdas status x code: fraude observado vs esperado (dist. legit) ==')
d = q(con, "SELECT status || '_' || coalesce(code,'NULL') cell, count(*) FILTER (WHERE fraud) f, count(*) FILTER (WHERE NOT fraud) l FROM tx GROUP BY 1 ORDER BY 1")
p = d.l/d.l.sum(); nf = d.f.sum(); d['esp'] = nf*p; d['z'] = (d.f-d.esp)/np.sqrt(d.esp*(1-p))
print(d.round(2).to_string(index=False))
X2 = ((d.f-d.esp)**2/d.esp).sum(); k = len(d)
print(f'chi2 bondad de ajuste = {X2:.2f} gl={k-1} p={1-chi2d.cdf(X2, k-1):.3f}')
rng = np.random.default_rng(1); sims = rng.multinomial(nf, p.values, size=20000)
zs = np.abs((sims - nf*p.values)/np.sqrt(nf*p.values*(1-p.values))).max(1)
zmax = np.abs(d.z).max()
print(f'max|z| observado={zmax:.2f} (celda {d.cell[np.abs(d.z).idxmax()]}); p familiar (simulación, 17 celdas)={np.mean(zs>=zmax):.3f}')

print('\n== (f) Estado de la tx siguiente según la previa (mismo producto y mismo cliente), población completa ==')
for part in ['product_id', 'customer_id']:
    d = q(con, f"""WITH s AS (SELECT status, lag(fraud) OVER (PARTITION BY {part} ORDER BY ts, transaction_id) pf,
        lag(status) OVER (PARTITION BY {part} ORDER BY ts, transaction_id) ps FROM tx)
      SELECT pf, count(*) n, sum((status='Declined')::int) dcl, sum((status<>'Approved')::int) na FROM s WHERE pf IS NOT NULL GROUP BY 1""").set_index('pf')
    r, lo, hi = rr_ci(d.loc[True, 'dcl'], d.loc[True, 'n'], d.loc[False, 'dcl'], d.loc[False, 'n'])
    r2, lo2, hi2 = rr_ci(d.loc[True, 'na'], d.loc[True, 'n'], d.loc[False, 'na'], d.loc[False, 'n'])
    print(f"  {part}: tras fraude n={d.loc[True,'n']:,} Declined {100*d.loc[True,'dcl']/d.loc[True,'n']:.2f}% vs tras legit n={d.loc[False,'n']:,} {100*d.loc[False,'dcl']/d.loc[False,'n']:.2f}%  RR={r:.3f}[{lo:.3f},{hi:.3f}] | no-Approved RR={r2:.3f}[{lo2:.3f},{hi2:.3f}]")
# placebo: la tx ANTERIOR a un fraude (lead) — si el efecto es real debería no aparecer
d = q(con, """WITH s AS (SELECT status, lead(fraud) OVER (PARTITION BY product_id ORDER BY ts, transaction_id) nf FROM tx)
  SELECT nf, count(*) n, sum((status='Declined')::int) dcl FROM s WHERE nf IS NOT NULL GROUP BY 1""").set_index('nf')
r, lo, hi = rr_ci(d.loc[True, 'dcl'], d.loc[True, 'n'], d.loc[False, 'dcl'], d.loc[False, 'n'])
print(f"  placebo (tx ANTERIOR a un fraude, producto): n={d.loc[True,'n']:,} Declined {100*d.loc[True,'dcl']/d.loc[True,'n']:.2f}% vs {100*d.loc[False,'dcl']/d.loc[False,'n']:.2f}% RR={r:.3f}[{lo:.3f},{hi:.3f}]")
# tras fraude_hi / fraude_lo específicamente
d = q(con, """WITH s AS (SELECT status, lag(CASE WHEN fraud AND fscore>30 THEN 'fraud_hi' WHEN fraud THEN 'fraud_lo' ELSE 'legit' END) OVER (PARTITION BY product_id ORDER BY ts, transaction_id) g FROM tx)
  SELECT g, count(*) n, round(100*avg((status='Declined')::int),3) pct_decl FROM s WHERE g IS NOT NULL GROUP BY 1 ORDER BY 1""")
print(d.to_string(index=False))

print('\n== (g) Dentro del fraude con score: AUC de fscore para el estado ==')
f = q(con, "SELECT customer_id, fscore, status FROM tx WHERE fraud AND fscore IS NOT NULL")
for name, y in [('Declined', (f.status == 'Declined').values), ('no-Approved', (f.status != 'Approved').values)]:
    s = f.fscore.values; auc = roc_auc_score(y, s)
    cust = f.customer_id.values; uc = np.unique(cust); idx = {c: np.where(cust == c)[0] for c in uc}
    rng = np.random.default_rng(0); bs = []
    for _ in range(500):
        pick = rng.choice(uc, len(uc)); ii = np.concatenate([idx[c] for c in pick])
        if y[ii].sum() in (0, len(ii)): continue
        bs.append(roc_auc_score(y[ii], s[ii]))
    print(f'  {name}: n={len(y)} pos={y.sum()} AUC={auc:.3f} IC95 bootstrap por cliente [{np.percentile(bs,2.5):.3f}, {np.percentile(bs,97.5):.3f}]')
