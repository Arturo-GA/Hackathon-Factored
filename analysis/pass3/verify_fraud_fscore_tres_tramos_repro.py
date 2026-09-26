"""Verificación independiente: fraud_score en tres tramos (>30 fraude, nulo = tasa base, <=30 sin información)."""
import duckdb, numpy as np, pandas as pd
from scipy.stats import kstest
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

print('== 1. Extremos por clase ==')
print(q("""SELECT fraud, count(*) n, count(fscore) n_scored, min(fscore) mn, max(fscore) mx,
  count(*) FILTER (WHERE fscore=30) eq30, count(*) FILTER (WHERE fscore>30) gt30,
  count(*) FILTER (WHERE fscore<=30) le30, count(*) FILTER (WHERE fscore IS NULL) nul,
  min(fscore) FILTER (WHERE fscore>30) min_gt30,
  count(*) FILTER (WHERE fscore=0) eq0,
  count(*) FILTER (WHERE round(fscore,2)<>fscore) not_2dec
  FROM tx GROUP BY 1""").to_string(index=False))

print('\n== 2. Umbrales ==')
tot = q("SELECT count(*) FILTER (WHERE fraud) p, count(*) FILTER (WHERE fraud AND fscore IS NOT NULL) ps FROM tx")
P, PS = int(tot.p[0]), int(tot.ps[0])
for thr in [25, 29.99, 30, 35, 40, 50]:
    d = q(f"SELECT count(*) FILTER (WHERE fscore>{thr} AND fraud) tp, count(*) FILTER (WHERE fscore>{thr}) pp FROM tx")
    tp, pp = int(d.tp[0]), int(d.pp[0])
    print(f">{thr}: tp={tp} pp={pp} prec={tp/pp:.4f} recall_total={tp/P:.4f} recall_scored={tp/PS:.4f}")
d = q("SELECT count(*) FILTER (WHERE fscore>=50 AND fraud) tp, count(*) FILTER (WHERE fscore>=50) pp FROM tx")
print(f">=50: tp={d.tp[0]} pp={d.pp[0]} recall_total={d.tp[0]/P:.4f} recall_scored={d.tp[0]/PS:.4f}")

print('\n== 3. Tramos ==')
t = q("""SELECT CASE WHEN fscore IS NULL THEN 'nulo' WHEN fscore<=30 THEN 'le30' ELSE 'gt30' END tramo,
  count(*) n, sum(fraud::int) f FROM tx GROUP BY 1""").set_index('tramo')
t['rate_pct'] = 100 * t.f / t.n
print(t)
r_nul = t.loc['nulo', 'f'] / t.loc['nulo', 'n']; r_le = t.loc['le30', 'f'] / t.loc['le30', 'n']
rr = r_nul / r_le
se = np.sqrt(1/t.loc['nulo','f'] - 1/t.loc['nulo','n'] + 1/t.loc['le30','f'] - 1/t.loc['le30','n'])
print(f"RR nulo/le30 = {rr:.3f}  IC95 [{np.exp(np.log(rr)-1.96*se):.3f}, {np.exp(np.log(rr)+1.96*se):.3f}]")
print('tasa base global %:', 100*P/t.n.sum(), ' esperado le30 si fraude~U(0,100): base*0.3/(1-0.7*base)')

print('\n== 4. Bins de 5 en [0,30] ==')
b = q("""SELECT least(floor(fscore/5),5)::int bin, count(*) n, sum(fraud::int) f, 100*avg(fraud::int) pct FROM tx
  WHERE fscore<=30 GROUP BY 1 ORDER BY 1""")
print(b.to_string(index=False))
# chi2 homogeneidad
from scipy.stats import chi2_contingency
ct = np.c_[b.f.values, (b.n - b.f).values]
print('chi2 homogeneidad bins:', chi2_contingency(ct)[:2])
# fraude por bin de 10 en (30,100]
print(q("""SELECT floor(fscore/10)::int bin10, count(*) FILTER (WHERE fraud) fr, count(*) FILTER (WHERE NOT fraud) leg
  FROM tx WHERE fscore IS NOT NULL GROUP BY 1 ORDER BY 1""").to_string(index=False))

print('\n== 5. AUC continuo dentro de [0,30] (Mann-Whitney agrupado por valor) ==')
g = q("""SELECT fscore v, count(*) FILTER (WHERE fraud) pos, count(*) FILTER (WHERE NOT fraud) neg FROM tx
  WHERE fscore<=30 GROUP BY 1 ORDER BY 1""")
def auc_grouped(g):
    cneg = g.neg.cumsum() - g.neg
    num = (g.pos * (cneg + 0.5 * g.neg)).sum()
    return num / (g.pos.sum() * g.neg.sum())
print('AUC fscore dentro de <=30:', round(auc_grouped(g), 4), ' n_pos=', int(g.pos.sum()))

print('\n== 6. MCAR del nulo ==')
for c in ['channel', 'ttype', 'status', 'currency', 'fraud']:
    d = q(f"SELECT {c} v, count(*) n, round(100*avg((fscore IS NULL)::int),2) pct_nulo FROM tx GROUP BY 1 ORDER BY 1")
    print(c, dict(zip(d.v.astype(str), d.pct_nulo)))
d = q("SELECT year(ts) y, round(100*avg((fscore IS NULL)::int),2) pct_nulo FROM tx GROUP BY 1 ORDER BY 1")
print('año', dict(zip(d.y, d.pct_nulo)))

print('\n== 7. KS ==')
leg = q("SELECT fscore FROM tx WHERE NOT fraud AND fscore IS NOT NULL USING SAMPLE 200000 ROWS (reservoir, 7)").fscore.values
fr = q("SELECT fscore FROM tx WHERE fraud AND fscore IS NOT NULL").fscore.values
print('legit vs U(0,30):', kstest(leg, 'uniform', args=(0, 30)))
print('fraude vs U(0,100):', kstest(fr, 'uniform', args=(0, 100)))
print('fraude<=30 vs U(0,30):', kstest(fr[fr <= 30], 'uniform', args=(0, 30)))

print('\n== 8. AUC por tramos, held-out agrupado por cliente + bootstrap por cliente ==')
cc = q("""SELECT customer_id, (hash(customer_id)%5=0) test,
  CASE WHEN fscore IS NULL THEN 1 WHEN fscore<=30 THEN 0 ELSE 2 END tr, fraud, count(*) n
  FROM tx GROUP BY ALL""")
tr_ = cc[~cc.test].groupby('tr').apply(lambda x: (x.n * x.fraud).sum() / x.n.sum())
print('posterior aprendido en train por tramo (0=le30,1=nulo,2=gt30):', tr_.round(6).to_dict())
te = cc[cc.test].copy()
te['s'] = te.tr.map(tr_)
def auc_from(df):
    g = df.groupby(['s', 'fraud']).n.sum().unstack(fill_value=0).sort_index()
    g.columns = ['neg' if not c else 'pos' for c in g.columns]
    return auc_grouped(g.reset_index())
a0 = auc_from(te)
custs = te.customer_id.unique(); rng = np.random.default_rng(0)
# agregar por cliente para bootstrap eficiente
te_idx = te.set_index('customer_id')
per = te.groupby(['customer_id', 's', 'fraud']).n.sum().reset_index()
cid_codes, uniq = pd.factorize(per.customer_id)
boots = []
for i in range(300):
    w = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))
    pw = per.assign(n=per.n * w[cid_codes])
    boots.append(auc_from(pw))
print(f"AUC test (tres tramos) = {a0:.4f} IC95 [{np.percentile(boots,2.5):.4f}, {np.percentile(boots,97.5):.4f}]  n_test={te.n.sum()} fraude_test={te[te.fraud].n.sum()}")
# AUC teórico con fscore>30 binario (sin distinguir nulo)
cc2 = te.assign(s=(te.tr == 2).astype(float))
print('AUC test solo indicador >30:', round(auc_from(cc2), 4))
