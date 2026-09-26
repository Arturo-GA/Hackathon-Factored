"""Verificador escéptico (reintento) — parte B: forma exacta de las distribuciones (datos completos, discretas a 0.01),
información del score dentro de [0,30], dígitos decimales, RR mecánico del nulo y MCAR por cliente."""
import sys; sys.path.insert(0, 'analysis/pass3')
import numpy as np, pandas as pd
from scipy.stats import chi2_contingency, chi2 as chi2d, kstwo, norm
from fraud_00_common import connect, q
pd.set_option('display.width', 220)
con = connect()

# ---------- B1. Bondad de ajuste con TODA la muestra, a nivel de valor (0.01) ----------
v = q(con, """SELECT round(fscore*100)::INT c, count(*) FILTER (WHERE NOT fraud) leg, count(*) FILTER (WHERE fraud) fr
              FROM tx WHERE fscore IS NOT NULL GROUP BY 1 ORDER BY 1""")
leg = v.set_index('c').leg.reindex(range(0, 3001), fill_value=0).values.astype(float)
nl = leg.sum()
# P(round(U(0,30),2)=c/100): interior 0.01/30, extremos 0.005/30
p = np.full(3001, 0.01 / 30); p[0] = p[-1] = 0.005 / 30
Femp = np.cumsum(leg) / nl; Fth = np.cumsum(p)
D = np.abs(Femp - Fth).max()
print('== B1. Legítimas vs U[0,30] redondeada a 0.01 (n=%d) ==' % nl)
print(f'KS discreto D={D:.5f}  D*sqrt(n)={D*np.sqrt(nl):.3f}  p_aprox={kstwo.sf(D, int(nl)):.3g}')
# chi2 en 30 bins de 1 punto con probabilidades exactas
bins = np.minimum(np.arange(3001) // 100, 29)
ob = np.bincount(bins, weights=leg); ex = np.bincount(bins, weights=p) * nl
c2 = ((ob - ex) ** 2 / ex).sum(); print(f'chi2 30 bins={c2:.1f} gl=29 p={chi2d.sf(c2, 29):.3f}; min/max obs/esp={ (ob/ex).min():.4f}/{(ob/ex).max():.4f}')
print('extremos: n(0.00)=%d n(30.00)=%d esperado=%.1f' % (leg[0], leg[-1], nl * 0.005 / 30))
# fraude vs U[0,100]
fr = v.set_index('c').fr.reindex(range(0, 10001), fill_value=0).values.astype(float); nf = fr.sum()
pf = np.full(10001, 0.01 / 100); pf[0] = pf[-1] = 0.005 / 100
Df = np.abs(np.cumsum(fr) / nf - np.cumsum(pf)).max()
print(f'Fraude vs U[0,100] (n={int(nf)}): KS D={Df:.4f} p={kstwo.sf(Df, int(nf)):.3f};  fracción <=30: {fr[:3001].sum()/nf:.4f} (esperado 0.3001)')
ob10 = np.bincount(np.minimum(np.arange(10001) // 1000, 9), weights=fr)
print('fraude por decil de score:', ob10.astype(int).tolist(), ' chi2 p=%.3f' % chi2d.sf(((ob10 - nf/10)**2/(nf/10)).sum(), 9))

# ---------- B2. ¿El valor ordena el riesgo dentro de [0,30]? ----------
print('\n== B2. Dentro de [0,30] ==')
L = leg; Fr = fr[:3001]
lr = (Fr / Fr.sum()) / np.where(L > 0, L / L.sum(), np.nan)
b5 = np.minimum(np.arange(3001) // 500, 5)
t5 = pd.DataFrame({'bin5': range(6), 'leg': np.bincount(b5, weights=L).astype(int), 'fr': np.bincount(b5, weights=Fr).astype(int)})
t5['pct_fraude'] = 100 * t5.fr / (t5.fr + t5.leg); print(t5.to_string(index=False))
print('chi2 homogeneidad 6 bins p=%.3f' % chi2_contingency(np.c_[t5.fr, t5.leg])[1])
b1 = np.minimum(np.arange(3001) // 100, 29)
f1 = np.bincount(b1, weights=Fr); l1 = np.bincount(b1, weights=L)
print('chi2 homogeneidad 30 bins p=%.3f' % chi2_contingency(np.c_[f1, l1])[1])
# tendencia (Cochran-Armitage) con score = punto medio del bin de 1
x = np.arange(30) + 0.5; n1 = f1 + l1; pbar = f1.sum() / n1.sum()
T = (x * (f1 - n1 * pbar)).sum(); VarT = pbar * (1 - pbar) * ((n1 * x**2).sum() - (n1 * x).sum()**2 / n1.sum())
print(f'Cochran-Armitage z={T/np.sqrt(VarT):.2f} p={2*norm.sf(abs(T/np.sqrt(VarT))):.3f}')
# AUC exacto (Mann-Whitney) dentro de <=30 + bootstrap por cliente sobre los casos de fraude (la CDF legítima, n=3.5M, se fija)
Fl = np.cumsum(L) / L.sum(); Fl_lt = Fl - L / L.sum()
auc_val = Fl_lt + 0.5 * L / L.sum()          # contribución de un fraude con valor c
frl = q(con, "SELECT customer_id, round(fscore*100)::INT c FROM tx WHERE fraud AND fscore<=30")
frl['a'] = auc_val[frl.c.values]
auc = frl.a.mean()
print('fraudes <=30:', len(frl), ' clientes distintos:', frl.customer_id.nunique())
g = frl.groupby('customer_id').a.agg(['sum', 'count']).values
rng = np.random.default_rng(1); bs = []
for _ in range(2000):
    i = rng.integers(0, len(g), len(g)); bs.append(g[i, 0].sum() / g[i, 1].sum())
print(f'AUC del valor dentro de <=30 = {auc:.4f} IC95 [{np.percentile(bs,2.5):.4f}, {np.percentile(bs,97.5):.4f}]; media fscore fraude<=30={(frl.c/100).mean():.2f} vs legit={(np.arange(3001)/100*L).sum()/L.sum():.2f}')

# ---------- B3. Dígitos decimales (¿huella distinta del generador por clase?) ----------
print('\n== B3. Dígitos decimales, solo <=30 ==')
d = q(con, """SELECT fraud, (round(fscore*100)::INT)%10 d2, ((round(fscore*100)::INT)//10)%10 d1, count(*) n
              FROM tx WHERE fscore<=30 GROUP BY ALL""")
for col in ['d2', 'd1']:
    ct = d.groupby([col, 'fraud']).n.sum().unstack(fill_value=0)
    print(col, 'fraude:', ct[True].tolist(), ' chi2 p=%.3f' % chi2_contingency(ct.values)[1])
ints = q(con, "SELECT fraud, avg((fscore=round(fscore))::INT) pct_enteros, avg((fscore*10=round(fscore*10))::INT) pct_1dec, count(*) n FROM tx WHERE fscore<=30 GROUP BY 1")
print(ints.to_string(index=False))

# ---------- B4. Tramos: RR observado vs mecánico ----------
print('\n== B4. Tramos, RR y expectativa mecánica ==')
t = q(con, """SELECT CASE WHEN fscore IS NULL THEN 'nulo' WHEN fscore<=30 THEN 'le30' ELSE 'gt30' END tramo, count(*) n, sum(fraud::int) f
              FROM tx GROUP BY 1""").set_index('tramo')
N, Fn = t.n.sum(), t.f.sum(); base = Fn / N
r = t.f / t.n
def rr_ci(a, na, b, nb):
    rr = (a/na)/(b/nb); se = np.sqrt(1/a - 1/na + 1/b - 1/nb); return rr, np.exp(np.log(rr)-1.96*se), np.exp(np.log(rr)+1.96*se)
print('tasas %:', (100*r).round(4).to_dict(), ' base %:', round(100*base, 4))
print('RR nulo/le30 = %.3f [%.3f, %.3f]' % rr_ci(t.f['nulo'], t.n['nulo'], t.f['le30'], t.n['le30']))
print('RR nulo/resto con score (<=30 y >30) = %.3f [%.3f, %.3f]' % rr_ci(t.f['nulo'], t.n['nulo'], t.f['le30']+t.f['gt30'], t.n['le30']+t.n['gt30']))
print('RR le30/base = %.3f ; nulo/base = %.3f' % (r['le30']/base, r['nulo']/base))
pnull_f = t.f['nulo'] / Fn; pnull_l = (t.n['nulo'] - t.f['nulo']) / (N - Fn)
print(f'P(nulo|fraude)={pnull_f:.4f}  P(nulo|legit)={pnull_l:.4f}')
# Modelo mecánico: nulo MCAR al 20%, fraude~U(0,100) => P(<=30|F)=0.8*0.3, P(<=30|L)=0.8  => RR = (0.2/0.2)/(0.24/0.8)=3.33
print('RR mecánico esperado (MCAR 20%% + fraude U(0,100), legit U(0,30)) = %.3f' % ((0.2/0.2)/(0.8*0.3/0.8)))
print('diferencia absoluta nulo - le30 = %.4f pp; 1 fraude cada %.0f (nulo) vs %.0f (le30)' % (100*(r['nulo']-r['le30']), 1/r['nulo'], 1/r['le30']))

# ---------- B5. MCAR del nulo: estratos y sobredispersión por cliente ----------
print('\n== B5. MCAR ==')
for c in ['channel', 'ttype', 'status', 'country', 'currency', "year(ts)", "(amount_usd IS NULL)", "(code IS NULL)"]:
    dd = q(con, f"SELECT {c} v, count(*) n, 100*avg((fscore IS NULL)::INT) pct FROM tx GROUP BY 1")
    print(f'{c:22s} % nulo min {dd.pct.min():.2f} max {dd.pct.max():.2f} (estratos={len(dd)})')
pc = q(con, """WITH c AS (SELECT customer_id, count(*) n, sum((fscore IS NULL)::INT) x FROM tx GROUP BY 1),
                  p AS (SELECT sum(x)/sum(n) p FROM c)
               SELECT count(*) k, sum((x - n*p)*(x - n*p)/(n*p*(1-p))) pearson FROM c, p""")
k, P = int(pc.k[0]), float(pc.pearson[0])
print(f'Sobredispersión por cliente: Pearson/gl = {P/(k-1):.4f} (1 = binomial pura; clientes={k}); p={chi2d.sf(P, k-1):.3f}')
pp = q(con, """WITH c AS (SELECT product_id, count(*) n, sum((fscore IS NULL)::INT) x FROM tx GROUP BY 1),
                  p AS (SELECT sum(x)/sum(n) p FROM c)
               SELECT count(*) k, sum((x - n*p)*(x - n*p)/(n*p*(1-p))) pearson FROM c, p""")
print(f'Sobredispersión por producto: Pearson/gl = {float(pp.pearson[0])/(int(pp.k[0])-1):.4f}')
