"""Verificación independiente (reintento) del hallazgo fraud_fscore_tres_tramos.

Calcula desde cero: extremos por clase, umbrales, tramos (nulo / <=30 / >30), planitud dentro de [0,30],
KS con corrección por redondeo a 2 decimales, MCAR del nulo, estabilidad por año/país y AUC en held-out
agrupado por cliente (split propio: hash(customer_id||'#v2') % 10 < 3) con bootstrap por cliente.
"""
import time
import duckdb, numpy as np, pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier

pd.set_option('display.width', 220); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()
T0 = time.time()


def auc_hist(pos, neg):
    """AUC (Mann-Whitney con empates=0.5) a partir de conteos por grupo de score ordenado ascendente."""
    pos = np.asarray(pos, float); neg = np.asarray(neg, float)
    below = np.cumsum(neg) - neg
    return float((pos * (below + 0.5 * neg)).sum() / (pos.sum() * neg.sum()))


# ---------------- 0. Totales ----------------
t0 = Q("""SELECT count(*) n, sum(fraud::INT) f, count(fscore) nsc, sum((fraud AND fscore IS NOT NULL)::INT) fsc,
          sum((fscore IS NOT NULL AND abs(fscore*100 - round(fscore*100)) > 1e-7)::INT) no2dec,
          sum((fscore<0 OR fscore>100)::INT) fuera, count(*) - count(fraud) fraud_null FROM tx""").iloc[0]
N, F, NSC, FSC = int(t0.n), int(t0.f), int(t0.nsc), int(t0.fsc)
L = N - F
print(f"N={N:,} fraude={F:,} legit={L:,} con_score={NSC:,} ({100*NSC/N:.2f}%) fraude_con_score={FSC:,} "
      f"valores_no_2dec={int(t0.no2dec)} fuera_0_100={int(t0.fuera)} fraud_nulo={int(t0.fraud_null)}")

# ---------------- 1. Histograma exacto por valor (k = fscore*100) ----------------
h = Q("""SELECT round(fscore*100)::INT k, sum(fraud::INT) pos, sum((NOT fraud)::INT) neg
         FROM tx WHERE fscore IS NOT NULL GROUP BY 1 ORDER BY 1""")
h[['pos', 'neg']] = h[['pos', 'neg']].astype(np.int64)
h = h.sort_values('k').reset_index(drop=True)
leg = h[h.neg > 0]; fr = h[h.pos > 0]
print('\n== 1. Extremos por clase ==')
print(f"legit: n_scored={int(h.neg.sum()):,} min={leg.k.min()/100:.2f} max={leg.k.max()/100:.2f} "
      f"n(0.00)={int(h.loc[h.k==0,'neg'].sum())} n(30.00)={int(h.loc[h.k==3000,'neg'].sum())} "
      f"n(>30)={int(h.loc[h.k>3000,'neg'].sum())} valores_distintos={len(leg)}")
print(f"fraude: n_scored={int(h.pos.sum()):,} min={fr.k.min()/100:.2f} max={fr.k.max()/100:.2f} "
      f"min(>30)={fr.k[fr.k>3000].min()/100:.2f} max(<=30)={fr.k[fr.k<=3000].max()/100:.2f} "
      f"n(30.00)={int(h.loc[h.k==3000,'pos'].sum())} valores_distintos={len(fr)}")

# ---------------- 2. Umbrales ----------------
print('\n== 2. Umbrales (recall_total = sobre todo el fraude, incl. score nulo) ==')
rows = {}
for t in [0, 10, 20, 25, 29, 29.99, 30, 35, 40, 45, 50]:
    m = h.k > round(t * 100)
    tp = int(h.pos[m].sum()); pp = tp + int(h.neg[m].sum())
    rows[f'>{t}'] = dict(tp=tp, pp=pp, prec=tp / pp, rec_total=tp / F, rec_scored=tp / FSC, f1=2 * tp / (pp + F))
m = h.k >= 5000; tp = int(h.pos[m].sum()); pp = tp + int(h.neg[m].sum())
rows['>=50'] = dict(tp=tp, pp=pp, prec=tp / pp, rec_total=tp / F, rec_scored=tp / FSC, f1=2 * tp / (pp + F))
print(pd.DataFrame(rows).T.round(4).to_string())
hs = h.sort_values('k', ascending=False)
tp_c = hs.pos.cumsum().values; pp_c = (hs.pos + hs.neg).cumsum().values
f1 = 2 * tp_c / (pp_c + F); i = int(np.argmax(f1))
print(f"umbral F1-óptimo (barrido exhaustivo): score >= {hs.k.values[i]/100:.2f} (F1={f1[i]:.4f}, prec={tp_c[i]/pp_c[i]:.4f}, rec_total={tp_c[i]/F:.4f})")
print(f"menor umbral con precisión 100%: > {leg.k.max()/100:.2f}")
print(f"recall >30 / recall >50 = {rows['>30']['tp']/rows['>50']['tp']:.3f}  ;  >30 / >=50 = {rows['>30']['tp']/rows['>=50']['tp']:.3f}")

# ---------------- 3. Tramos ----------------
print('\n== 3. Tramos ==')
tr = Q("""SELECT CASE WHEN fscore IS NULL THEN 'nulo' WHEN fscore<=30 THEN '<=30' ELSE '>30' END tramo,
          count(*) n, sum(fraud::INT) f FROM tx GROUP BY 1""").set_index('tramo')
tr['tasa_%'] = 100 * tr.f / tr.n; tr['share_fraude_%'] = 100 * tr.f / F; tr['share_tx_%'] = 100 * tr.n / N
print(tr.round(4).to_string())
a, n1, c, n2 = [float(x) for x in (tr.loc['nulo', 'f'], tr.loc['nulo', 'n'], tr.loc['<=30', 'f'], tr.loc['<=30', 'n'])]
rr = (a / n1) / (c / n2); se = np.sqrt(1 / a - 1 / n1 + 1 / c - 1 / n2)
print(f"RR nulo/<=30 = {rr:.3f} IC95 [{rr*np.exp(-1.96*se):.3f}, {rr*np.exp(1.96*se):.3f}]  (teórico si legit~U(0,30) y fraude~U(0,100): ~1/0.3=3.33)")
rb = (a / n1) / (F / N); seb = np.sqrt(1 / a - 1 / n1 + 1 / F - 1 / N)
print(f"tasa base global={100*F/N:.4f}% ; tasa nulo / base = {rb:.3f} (IC95 aprox [{rb*np.exp(-1.96*seb):.3f}, {rb*np.exp(1.96*seb):.3f}])")
print(f"P(legit | <=30) = {100*(1-c/n2):.3f}%")

# ---------------- 4. Dentro de [0,30] ----------------
print('\n== 4. Dentro de [0,30] ==')
w = h[h.k <= 3000].copy()
w['b5'] = np.minimum(w.k // 500, 5)
b5 = w.groupby('b5')[['pos', 'neg']].sum(); b5['tasa_%'] = 100 * b5.pos / (b5.pos + b5.neg)
b5.index = [f'[{5*i},{5*i+5}{"]" if i == 5 else ")"}' for i in b5.index]
print(b5.round(4).T.to_string())
chi = stats.chi2_contingency(b5[['pos', 'neg']].values)
print(f"chi2 homogeneidad 6 bins: chi2={chi[0]:.2f} df={chi[2]} p={chi[1]:.3f}")
w['b1'] = np.minimum(w.k // 100, 29)
b1 = w.groupby('b1')[['pos', 'neg']].sum(); r1 = 100 * b1.pos / (b1.pos + b1.neg)
chi1 = stats.chi2_contingency(b1.values)
print(f"30 bins de 1 punto: tasa min={r1.min():.4f}% max={r1.max():.4f}% chi2={chi1[0]:.1f} df={chi1[2]} p={chi1[1]:.3f}")
auc_in = auc_hist(w.pos.values, w.neg.values)
pos_rows = Q("SELECT customer_id, round(fscore*100)::INT k FROM tx WHERE fraud AND fscore<=30")
negc = w.set_index('k').neg.reindex(range(3001), fill_value=0)
place = ((negc.cumsum() - negc) + 0.5 * negc) / negc.sum()
pos_rows['V'] = place.reindex(pos_rows.k).values
assert pos_rows.V.notna().all()
g = pos_rows.groupby('customer_id').V.agg(['sum', 'count'])
se_auc = np.sqrt(((g['sum'] - auc_in * g['count']) ** 2).sum()) / len(pos_rows)
print(f"AUC del valor del score dentro de <=30 = {auc_in:.4f} IC95 [{auc_in-1.96*se_auc:.4f}, {auc_in+1.96*se_auc:.4f}] "
      f"(n_pos={len(pos_rows)}, clientes={len(g)}, SE agrupado por cliente)")
lo = w[w.k < 1500][['pos', 'neg']].sum(); hi = w[w.k >= 1500][['pos', 'neg']].sum()
rr2 = (hi.pos / (hi.pos + hi.neg)) / (lo.pos / (lo.pos + lo.neg))
se2 = np.sqrt(1 / hi.pos - 1 / (hi.pos + hi.neg) + 1 / lo.pos - 1 / (lo.pos + lo.neg))
print(f"RR tasa [15,30] vs [0,15) = {rr2:.3f} IC95 [{rr2*np.exp(-1.96*se2):.3f}, {rr2*np.exp(1.96*se2):.3f}]")

# ---------------- 5. Uniformidad ----------------
print('\n== 5. Uniformidad ==')
lk = w.set_index('k').neg.reindex(range(3001), fill_value=0)
nL = int(lk.sum())
ecdf = lk.cumsum().values / nL
K = np.arange(3001)
G = np.where(K < 3000, (K + 0.5) / 3000, 1.0)  # CDF exacta de round(U(0,30), 2)
D_full = float(np.abs(ecdf - G).max())
print(f"legit, población completa (n={nL:,}) vs U(0,30) redondeada a 2 dec: D={D_full:.5f} "
      f"p≈{stats.kstwobign.sf(D_full*np.sqrt(nL)):.3g} (crítico 5%={1.358/np.sqrt(nL):.5f})")
print(f"  esperado en 0.00 y en 30.00 (medio intervalo de redondeo): {nL*0.5/3000:.0f} c/u; observado {int(lk[0])} y {int(lk[3000])}")
exp1 = np.array([99.5] + [100] * 28 + [100.5]) / 3000 * nL
obs1 = b1.neg.values.astype(float)
c2 = float(((obs1 - exp1) ** 2 / exp1).sum())
print(f"  chi2 30 bins legit vs uniforme: {c2:.1f} df=29 p={stats.chi2.sf(c2, 29):.3f}")
rng = np.random.default_rng(11)
samp = rng.choice(lk.index.values, size=200_000, p=lk.values / nL) / 100
ks_s = stats.kstest(samp, 'uniform', args=(0, 30))
print(f"  kstest continuo sobre muestra 200k (como el original): D={ks_s.statistic:.4f} p={ks_s.pvalue:.3f}")
fk = np.repeat(fr.k.values, fr.pos.values) / 100
k1 = stats.kstest(fk, 'uniform', args=(0, 100)); k2 = stats.kstest(fk[fk <= 30], 'uniform', args=(0, 30))
k3 = stats.kstest(fk[fk > 30], 'uniform', args=(30, 70))
print(f"fraude con score (n={len(fk)}): KS vs U(0,100) D={k1.statistic:.4f} p={k1.pvalue:.3f}; "
      f"<=30 vs U(0,30) D={k2.statistic:.4f} p={k2.pvalue:.3f}; >30 vs U(30,100) D={k3.statistic:.4f} p={k3.pvalue:.3f}")
c10 = np.histogram(fk, bins=np.arange(0, 101, 10))[0]
print(f"  fraude por decil de score: {c10.tolist()}  chi2 p={stats.chisquare(c10).pvalue:.3f}")
bt = stats.binomtest(int((fk > 30).sum()), len(fk), 0.70)
print(f"  fracción del fraude con score que está >30: {(fk>30).mean():.4f} (esperado 0.70 si U(0,100); p={bt.pvalue:.3f})")

# ---------------- 6. Nulo MCAR ----------------
print('\n== 6. ¿Nulo MCAR? (% de fscore nulo por nivel) ==')
for col in ['channel', 'ttype', 'status', 'currency', 'country', 'year(ts)', "coalesce(code,'NA')", 'tcat', 'fraud']:
    d = Q(f"SELECT ({col})::VARCHAR v, count(*) n, 100*avg((fscore IS NULL)::INT) p FROM tx GROUP BY 1 ORDER BY 1")
    d = d[d.n >= 5000] if col != 'fraud' else d
    extra = {k: round(v, 2) for k, v in zip(d.v, d.p)} if len(d) <= 7 else f'({len(d)} niveles con n>=5000)'
    print(f"  {col}: rango {d.p.min():.2f}–{d.p.max():.2f}%  {extra}")
d = Q("""WITH q AS (SELECT currency, approx_quantile(amount, [0.2,0.4,0.6,0.8]) qq FROM tx GROUP BY 1)
SELECT CASE WHEN amount < qq[1] THEN 1 WHEN amount < qq[2] THEN 2 WHEN amount < qq[3] THEN 3 WHEN amount < qq[4] THEN 4 ELSE 5 END quint,
 count(*) n, 100*avg((fscore IS NULL)::INT) p FROM tx JOIN q USING (currency) GROUP BY 1 ORDER BY 1""")
print(f"  quintil de monto (dentro de moneda): {dict(zip(d.quint, d.p.round(2)))}")
fn = Q("SELECT fraud, count(*) n, sum((fscore IS NULL)::INT) k FROM tx GROUP BY 1").set_index('fraud')
p1_, p0_ = fn.loc[True, 'k'] / fn.loc[True, 'n'], fn.loc[False, 'k'] / fn.loc[False, 'n']
pp_ = fn.k.sum() / fn.n.sum(); z = (p1_ - p0_) / np.sqrt(pp_ * (1 - pp_) * (1 / fn.loc[True, 'n'] + 1 / fn.loc[False, 'n']))
print(f"  nulo en fraude {100*p1_:.2f}% ({int(fn.loc[True,'k'])}/{int(fn.loc[True,'n'])}) vs legit {100*p0_:.2f}%: z={z:.2f} p={2*stats.norm.sf(abs(z)):.3f}")
for key in ['customer_id', 'product_id']:
    d = Q(f"""WITH p AS (SELECT avg((fscore IS NULL)::INT) p FROM tx),
      c AS (SELECT {key}, count(*) n, sum((fscore IS NULL)::INT) k FROM tx GROUP BY 1)
      SELECT count(*) nc, sum((k - n*p)*(k - n*p)/(n*p*(1-p))) chi2 FROM c, p""").iloc[0]
    print(f"  dispersión del nulo por {key}: chi2/df = {d.chi2/(d.nc-1):.4f} (1 = sin agrupamiento; n={int(d.nc):,})")

# ---------------- 6b. Estabilidad de la regla ----------------
print('\n== 6b. Estabilidad de la regla por año y país ==')
for col in ['year(ts)', 'country', 'currency', 'status']:
    d = Q(f"""SELECT ({col})::VARCHAR v, max(fscore) FILTER (WHERE NOT fraud) max_leg,
      sum((NOT fraud AND fscore>30)::INT) fp, sum((fraud AND fscore>30)::INT) tp, sum(fraud::INT) f
      FROM tx GROUP BY 1 HAVING count(*)>=5000 ORDER BY 1""")
    d['rec'] = (d.tp / d.f).round(3)
    print(f"  {col}: max_leg∈[{d.max_leg.min():.2f},{d.max_leg.max():.2f}] fp_total={int(d.fp.sum())} recall por nivel∈[{d.rec.min():.3f},{d.rec.max():.3f}] ({len(d)} niveles)")

# ---------------- 7. AUC held-out agrupado por cliente ----------------
print('\n== 7. AUC en held-out (30% de clientes por hash propio) ==')
agg = Q("""SELECT (hash(customer_id || '#v2') % 10 < 3) test, coalesce(round(fscore*100)::INT, -100) k,
          sum(fraud::INT) pos, sum((NOT fraud)::INT) neg FROM tx GROUP BY ALL""")
agg[['pos', 'neg']] = agg[['pos', 'neg']].astype(float)
trn = agg[~agg.test].groupby('k')[['pos', 'neg']].sum(); tst = agg[agg.test].groupby('k')[['pos', 'neg']].sum()
print(f"train n={int(trn.values.sum()):,} fraude={int(trn.pos.sum())} | test n={int(tst.values.sum()):,} fraude={int(tst.pos.sum())}")

# (a) regla aprendida en train y aplicada en test
thr = trn.index[(trn.neg > 0) & (trn.index >= 0)].max()
for name, mask in [(f'>{thr/100:.2f} (aprendido en train)', tst.index > thr), ('>50 (baseline)', tst.index > 5000), ('>=50', tst.index >= 5000)]:
    tp = tst.pos[mask].sum(); pp = tp + tst.neg[mask].sum()
    print(f"  test regla {name}: precisión {int(tp)}/{int(pp)} = {tp/pp:.4f}; recall total {tp/tst.pos.sum():.4f}")

# (b) tres tramos: posterior aprendido en train, AUC en test + bootstrap exacto por cliente
tramo = lambda k: np.where(k < 0, 1, np.where(k <= 3000, 0, 2))
ptr = trn.groupby(tramo(trn.index.values))[['pos', 'neg']].sum()
post = ptr.pos / (ptr.pos + ptr.neg)
print(f"  posterior train por tramo (0:<=30, 1:nulo, 2:>30): {post.round(6).to_dict()}")
order = post.sort_values().index.tolist()
pte = tst.groupby(tramo(tst.index.values))[['pos', 'neg']].sum().reindex(order)
auc3 = auc_hist(pte.pos, pte.neg)
pc = Q("""SELECT customer_id,
  sum((fraud AND fscore<=30)::INT) p0, sum((NOT fraud AND fscore<=30)::INT) n0,
  sum((fraud AND fscore IS NULL)::INT) p1, sum((NOT fraud AND fscore IS NULL)::INT) n1,
  sum((fraud AND fscore>30)::INT) p2, sum((NOT fraud AND fscore>30)::INT) n2
  FROM tx WHERE hash(customer_id || '#v2') % 10 < 3 GROUP BY 1""")
Pm = pc[[f'p{i}' for i in order]].values.astype(float); Nm = pc[[f'n{i}' for i in order]].values.astype(float)
rng = np.random.default_rng(5); C = len(pc); boots = []
for _ in range(1000):
    wv = np.bincount(rng.integers(0, C, C), minlength=C).astype(float)
    boots.append(auc_hist(wv @ Pm, wv @ Nm))
print(f"  AUC 3 tramos (test) = {auc3:.4f} IC95 [{np.percentile(boots,2.5):.4f}, {np.percentile(boots,97.5):.4f}] (bootstrap 1000 por cliente, C={C:,})")

# (c) score crudo monótono con nulo=-1 (sin modelo)
print(f"  AUC score crudo monótono (nulo=-1, test) = {auc_hist(tst.pos, tst.neg):.4f}")

# (d) GBM solo con fscore (nulo=-1), entrenado con pesos sobre la tabla agregada del train
Xk = np.where(trn.index.values < 0, -1.0, trn.index.values / 100)
Xa = np.r_[Xk, Xk].reshape(-1, 1); ya = np.r_[np.ones(len(Xk)), np.zeros(len(Xk))]; wa = np.r_[trn.pos.values, trn.neg.values]
keep = wa > 0
gbm = HistGradientBoostingClassifier(random_state=0).fit(Xa[keep], ya[keep], sample_weight=wa[keep])
keys = np.union1d(trn.index.values, tst.index.values)
pmap = pd.Series(gbm.predict_proba(np.where(keys < 0, -1.0, keys / 100).reshape(-1, 1))[:, 1], index=keys).round(12)
st = tst.assign(s=pmap.reindex(tst.index).values).groupby('s')[['pos', 'neg']].sum().sort_index()
sr = trn.assign(s=pmap.reindex(trn.index).values).groupby('s')[['pos', 'neg']].sum().sort_index()
auc_gbm = auc_hist(st.pos, st.neg)
print(f"  GBM: valores distintos de predicción={pmap.nunique()}, pred(nulo)={pmap[-100]:.5f}, "
      f"pred media <=30={pmap[(pmap.index>=0)&(pmap.index<=3000)].mean():.5f}, pred min >30={pmap[pmap.index>3000].min():.4f}")
mapg = pd.DataFrame({'k': keys.astype(np.int32), 'g': pmap.rank(method='dense').astype(np.int32).values})
con.register('mapg', mapg)
t1 = time.time()
R = 200
bt = Q(f"""
WITH t AS (SELECT hash(customer_id) hc, coalesce(round(fscore*100)::INT, -100) k, fraud::INT y, count(*) n
           FROM tx WHERE hash(customer_id || '#v2') % 10 < 3 GROUP BY ALL),
t2 AS (SELECT hc, g, y, sum(n) n FROM t JOIN mapg USING (k) GROUP BY ALL),
w AS (SELECT r.b, g, y, n, (hash(hc, r.b) % 1000000)::DOUBLE / 1e6 u FROM t2 CROSS JOIN range({R}) r(b))
SELECT b, g, y, sum(n * CASE WHEN u < 0.3678794 THEN 0 WHEN u < 0.7357589 THEN 1 WHEN u < 0.9196986 THEN 2
    WHEN u < 0.9810118 THEN 3 WHEN u < 0.9963402 THEN 4 WHEN u < 0.9994058 THEN 5 ELSE 6 END)::BIGINT nw
FROM w GROUP BY ALL""")
gb = []
for b, d in bt.groupby('b'):
    pv = d.pivot_table(index='g', columns='y', values='nw', aggfunc='sum', fill_value=0).sort_index()
    gb.append(auc_hist(pv.get(1, 0 * pv[0]), pv[0]))
print(f"  AUC GBM solo fscore (test) = {auc_gbm:.4f} IC95 [{np.percentile(gb,2.5):.4f}, {np.percentile(gb,97.5):.4f}] "
      f"(bootstrap Poisson por cliente R={R}, {time.time()-t1:.0f}s); AUC GBM en train = {auc_hist(sr.pos, sr.neg):.4f}")

# (e) AUC teórico con las proporciones de la población completa
fg = tr.f / F; lg = (tr.n - tr.f) / L
auc_th = fg['>30'] * 1 + fg['nulo'] * (lg['<=30'] + 0.5 * lg['nulo']) + fg['<=30'] * 0.5 * lg['<=30']
print(f"  AUC teórico (ranking >30 > nulo > <=30, sin orden dentro de <=30), población completa = {auc_th:.4f}")
print(f"\nTiempo total {time.time()-T0:.0f}s")
