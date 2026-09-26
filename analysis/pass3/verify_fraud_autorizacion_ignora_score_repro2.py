"""Verificación independiente (reintento) del hallazgo fraud_autorizacion_ignora_score.
Afirmación: status y code son independientes de fraud y de fscore; el fraude se aprueba igual que lo legítimo.
Se recalcula todo desde cero con SQL agregado (sin reutilizar los scripts originales)."""
import numpy as np, pandas as pd, duckdb
from scipy.stats import chi2_contingency, rankdata

pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()


def cramer(ct):
    ct = np.asarray(ct, float); ct = ct[ct.sum(1) > 0][:, ct.sum(0) > 0]
    chi2, p, dof, _ = chi2_contingency(ct, correction=False)
    return chi2, p, dof, np.sqrt(chi2 / (ct.sum() * (min(ct.shape) - 1)))


def rr(a, n1, b, n0):
    r = (a / n1) / (b / n0); se = np.sqrt(1 / a - 1 / n1 + 1 / b - 1 / n0)
    return r, np.exp(np.log(r) - 1.96 * se), np.exp(np.log(r) + 1.96 * se)


print('== 0. Universo ==')
print(Q("""SELECT count(*) n, count(*) FILTER (WHERE fraud IS NULL) fraud_null, sum(fraud::INT) n_fraud,
  count(*) FILTER (WHERE status IS NULL) status_null, min(ts) ts_min, max(ts) ts_max,
  max(fscore) FILTER (WHERE NOT fraud) max_fs_legit, min(fscore) FILTER (WHERE fraud AND fscore>30) min_fs_fr_gt30,
  count(*) FILTER (WHERE NOT fraud AND fscore>30) legit_gt30, count(*) FILTER (WHERE fraud AND fscore>30) fraud_gt30,
  count(*) FILTER (WHERE fraud AND fscore<=30) fraud_le30, count(*) FILTER (WHERE fraud AND fscore IS NULL) fraud_null_fs
  FROM tx""").T.to_string(header=False))

G = "CASE WHEN NOT fraud THEN 'a_legit' WHEN fscore>30 THEN 'b_fraud_gt30' ELSE 'c_fraud_le30_o_nulo' END"
print('\n== 1. status por grupo ==')
d = Q(f"SELECT {G} g, status, count(*) n FROM tx GROUP BY 1,2")
pv = d.pivot(index='g', columns='status', values='n').fillna(0).astype(int)
pv.loc['d_fraud_total'] = pv.loc['b_fraud_gt30'] + pv.loc['c_fraud_le30_o_nulo']
pv['N'] = pv[['Approved', 'Declined', 'Pending', 'Reversed']].sum(1)
print(pv.to_string())
pct = pv[['Approved', 'Declined', 'Pending', 'Reversed']].div(pv.N, axis=0) * 100
print(pct.round(3).to_string())
for s in ['Approved', 'Declined', 'Pending', 'Reversed']:
    for g in ['b_fraud_gt30', 'c_fraud_le30_o_nulo', 'd_fraud_total']:
        r, lo, hi = rr(pv.loc[g, s], pv.loc[g, 'N'], pv.loc['a_legit', s], pv.loc['a_legit', 'N'])
        print(f"  RR {s:8s} {g:20s} vs legit: {r:.3f} IC95[{lo:.3f},{hi:.3f}]  (n_evento={pv.loc[g, s]})")
ch = cramer(pv.loc[['a_legit', 'd_fraud_total'], ['Approved', 'Declined', 'Pending', 'Reversed']].values)
print('  status x fraud (2x4): chi2=%.2f p=%.3f dof=%d V=%.5f' % ch)
ch = cramer(pv.loc[['a_legit', 'b_fraud_gt30', 'c_fraud_le30_o_nulo'], ['Approved', 'Declined', 'Pending', 'Reversed']].values)
print('  status x grupo (3x4): chi2=%.2f p=%.3f dof=%d V=%.5f' % ch)

print('\n== 2. code por grupo (sobre total y sobre code no nulo) ==')
d = Q(f"SELECT {G} g, coalesce(code,'NULL') code, count(*) n FROM tx GROUP BY 1,2")
pc = d.pivot(index='g', columns='code', values='n').fillna(0).astype(int)
pc.loc['d_fraud_total'] = pc.loc['b_fraud_gt30'] + pc.loc['c_fraud_le30_o_nulo']
codes = list(pc.columns)
print(pc.to_string())
print('  % sobre total:'); print((pc[codes].div(pc[codes].sum(1), axis=0) * 100).round(3).to_string())
nn = [c for c in codes if c != 'NULL']
print('  % sobre code no nulo:'); print((pc[nn].div(pc[nn].sum(1), axis=0) * 100).round(3).to_string())
ch = cramer(pc.loc[['a_legit', 'd_fraud_total'], codes].values)
print('  code x fraud: chi2=%.2f p=%.3f dof=%d V=%.5f' % ch)
print('  status x code (todas las filas):')
print(Q("SELECT status, coalesce(code,'NULL') code, count(*) n FROM tx GROUP BY 1,2").pivot(index='status', columns='code', values='n').fillna(0).astype(int).to_string())

print('\n== 3. Tramos de fscore: status y code (todas las filas y solo legítimas) ==')
T = """CASE WHEN fscore IS NULL THEN 'nulo' WHEN fscore<=10 THEN '00-10' WHEN fscore<=20 THEN '10-20' WHEN fscore<=30 THEN '20-30'
 WHEN fscore<=60 THEN '30-60' ELSE '60-100' END"""
for filt, lab in [('TRUE', 'todas'), ('NOT fraud', 'legitimas'), ('fraud', 'fraude')]:
    t = Q(f"""SELECT {T} tramo, count(*) n, sum(fraud::INT) nf,
      round(100*avg((status='Approved')::INT),3) appr, round(100*avg((status='Declined')::INT),3) decl,
      round(100*avg((status='Pending')::INT),3) pend, round(100*avg((status='Reversed')::INT),3) rev,
      round(100*avg((code='00')::INT),3) c00, round(100*avg((code='05')::INT),3) c05, round(100*avg((code='14')::INT),3) c14,
      round(100*avg((code='51')::INT),3) c51, round(100*avg((code='54')::INT),3) c54, round(100*avg((code IS NULL)::INT),3) cnull
      FROM tx WHERE {filt} GROUP BY 1 ORDER BY 1""")
    print(f'-- {lab}'); print(t.to_string(index=False))
d = Q(f"SELECT {T} b, status, count(*) n FROM tx GROUP BY 1,2")
print('  status x tramo fscore (6 tramos+nulo, todas): chi2=%.2f p=%.3f dof=%d V=%.5f' % cramer(d.pivot(index='b', columns='status', values='n').fillna(0).values))
d = Q("""SELECT CASE WHEN fscore IS NULL THEN 'nulo' ELSE (floor(least(fscore,29.9999)))::VARCHAR END b, status, count(*) n
  FROM tx WHERE NOT fraud GROUP BY 1,2""")
print('  status x 30 bins de 1 punto + nulo (legit): chi2=%.2f p=%.3f dof=%d V=%.5f' % cramer(d.pivot(index='b', columns='status', values='n').fillna(0).values))
d = Q("""SELECT CASE WHEN fscore IS NULL THEN 'nulo' ELSE (floor(least(fscore,29.9999)))::VARCHAR END b, coalesce(code,'NULL') code, count(*) n
  FROM tx WHERE NOT fraud GROUP BY 1,2""")
print('  code x 30 bins de 1 punto + nulo (legit): chi2=%.2f p=%.3f dof=%d V=%.5f' % cramer(d.pivot(index='b', columns='code', values='n').fillna(0).values))

print('\n== 4. Correlaciones de fscore ==')
print(Q("""SELECT 'legit' g, count(*) n, corr(fscore, ln(1+amount)) r_ln1p_amt, corr(fscore, ln(amount)) FILTER (WHERE amount>0) r_ln_amt,
   corr(fscore, hour(ts)) r_hora, corr(fscore, amount) r_amt FROM tx WHERE NOT fraud AND fscore IS NOT NULL
  UNION ALL SELECT 'todas', count(*), corr(fscore, ln(1+amount)), corr(fscore, ln(amount)) FILTER (WHERE amount>0),
   corr(fscore, hour(ts)), corr(fscore, amount) FROM tx WHERE fscore IS NOT NULL
  UNION ALL SELECT 'fraude', count(*), corr(fscore, ln(1+amount)), corr(fscore, ln(amount)) FILTER (WHERE amount>0),
   corr(fscore, hour(ts)), corr(fscore, amount) FROM tx WHERE fraud AND fscore IS NOT NULL""").to_string(index=False))

print('\n== 5. AUC de fscore para predecir el estado (Mann-Whitney exacto en SQL, población completa) ==')
for filt, tgt in [('NOT fraud', "status='Declined'"), ('TRUE', "status='Declined'"), ('TRUE', "status<>'Approved'"),
                  ('fraud', "status='Declined'"), ('fraud', "status<>'Approved'")]:
    a = Q(f"""WITH s AS (SELECT fscore, ({tgt}) y FROM tx WHERE {filt} AND fscore IS NOT NULL),
      r AS (SELECT y, rank() OVER (ORDER BY fscore) + (count(*) OVER (PARTITION BY fscore) - 1)/2.0 rk FROM s)
      SELECT (sum(rk) FILTER (WHERE y) - count(*) FILTER (WHERE y)*(count(*) FILTER (WHERE y)+1)/2.0)
        / (count(*) FILTER (WHERE y)::DOUBLE * count(*) FILTER (WHERE NOT y)) auc, count(*) FILTER (WHERE y) npos, count(*) n FROM r""")
    print(f"  [{filt}] fscore -> {tgt}: AUC={a.auc[0]:.4f} npos={a.npos[0]:,} n={a.n[0]:,}")

# IC95 bootstrap agrupado por cliente (muestra de clientes por hash, ~5%)
rng = np.random.default_rng(7)
s = Q("""SELECT customer_id, fscore, (status='Declined')::INT y, (status<>'Approved')::INT y2 FROM tx
  WHERE fscore IS NOT NULL AND NOT fraud AND hash(customer_id) % 20 = 3""")
def auc(x, y):
    r = rankdata(x); n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
codes_c, inv = np.unique(s.customer_id.values, return_inverse=True)
order = np.argsort(inv, kind='stable'); starts = np.searchsorted(inv[order], np.arange(len(codes_c)))
ends = np.append(starts[1:], len(inv))
x = s.fscore.values; ys = {'Declined': s.y.values, 'NoAprobado': s.y2.values}
for lab, y in ys.items():
    base = auc(x, y); bs = []
    for _ in range(300):
        pick = rng.integers(0, len(codes_c), len(codes_c))
        idx = np.concatenate([order[starts[i]:ends[i]] for i in pick])
        bs.append(auc(x[idx], y[idx]))
    print(f"  muestra legit {len(s):,} filas / {len(codes_c):,} clientes: AUC fscore->{lab}={base:.4f} IC95 bootstrap cliente [{np.percentile(bs,2.5):.4f},{np.percentile(bs,97.5):.4f}]")
# dentro del fraude (todas las filas de fraude con score)
f = Q("SELECT customer_id, fscore, (status='Declined')::INT y, (status<>'Approved')::INT y2 FROM tx WHERE fraud AND fscore IS NOT NULL")
cf, invf = np.unique(f.customer_id.values, return_inverse=True)
of = np.argsort(invf, kind='stable'); sf = np.searchsorted(invf[of], np.arange(len(cf))); ef = np.append(sf[1:], len(invf))
for lab, y in {'Declined': f.y.values, 'NoAprobado': f.y2.values}.items():
    base = auc(f.fscore.values, y); bs = []
    for _ in range(1000):
        pick = rng.integers(0, len(cf), len(cf)); idx = np.concatenate([of[sf[i]:ef[i]] for i in pick])
        bs.append(auc(f.fscore.values[idx], y[idx]))
    print(f"  fraude con score {len(f):,} filas / {len(cf):,} clientes: AUC fscore->{lab}={base:.4f} IC95 [{np.percentile(bs,2.5):.4f},{np.percentile(bs,97.5):.4f}]")

print('\n== 6. Tasa de fraude por estado (‰) y RR vs Approved ==')
d = Q("SELECT status, count(*) n, sum(fraud::INT) f, sum((fraud AND fscore>30)::INT) fhi FROM tx GROUP BY 1 ORDER BY 1").set_index('status')
for st in d.index:
    r, lo, hi = rr(d.loc[st, 'f'], d.loc[st, 'n'], d.loc['Approved', 'f'], d.loc['Approved', 'n'])
    print(f"  {st:9s} n={d.loc[st,'n']:>9,} fraude={d.loc[st,'f']:>5,} ({1000*d.loc[st,'f']/d.loc[st,'n']:.3f}‰) RR={r:.3f} IC95[{lo:.3f},{hi:.3f}] fraude_gt30={d.loc[st,'fhi']}")

print('\n== 7. Estratos: Declined fraude vs legit por ttype, canal y país (RR Mantel-Haenszel) ==')
for col in ['ttype', 'channel', 'country']:
    d = Q(f"""SELECT {col} k, count(*) FILTER (WHERE fraud) nf, count(*) FILTER (WHERE fraud AND status='Declined') df,
      count(*) FILTER (WHERE NOT fraud) nl, count(*) FILTER (WHERE NOT fraud AND status='Declined') dl FROM tx GROUP BY 1 ORDER BY 1""")
    d['pf'] = 100 * d.df / d.nf; d['pl'] = 100 * d.dl / d.nl
    N = d.nf + d.nl
    mh = (d.df * d.nl / N).sum() / (d.dl * d.nf / N).sum()
    print(f"-- {col}: RR_MH={mh:.3f}; rango %Declined fraude [{d.pf.min():.2f},{d.pf.max():.2f}] vs legit [{d.pl.min():.2f},{d.pl.max():.2f}]")
    print(d[['k', 'nf', 'pf', 'nl', 'pl']].round(2).to_string(index=False))

print('\n== 8. Fraude con fscore>30 aprobado: total y ritmo mensual ==')
m = Q("""SELECT date_trunc('month', ts) mes, count(*) FILTER (WHERE fraud AND fscore>30) fr_gt30,
  count(*) FILTER (WHERE fraud AND fscore>30 AND status='Approved') fr_gt30_appr,
  count(*) FILTER (WHERE fraud AND fscore>30 AND status<>'Declined') fr_gt30_nodecl,
  count(*) FILTER (WHERE fraud AND status='Approved') fr_appr FROM tx GROUP BY 1 ORDER BY 1""")
dias = Q("SELECT date_diff('day', min(ts)::DATE, max(ts)::DATE) d FROM tx").d[0]
meses = dias / 30.4375
print(f"  días={dias}  meses={meses:.2f}  meses calendario con datos={len(m)}")
for c in ['fr_gt30', 'fr_gt30_appr', 'fr_gt30_nodecl', 'fr_appr']:
    tot = m[c].sum()
    print(f"  {c:15s} total={tot:>5,}  por mes={tot/meses:.1f}  (mediana mensual completa={m[c].iloc[1:-1].median():.0f}, min={m[c].iloc[1:-1].min()}, max={m[c].iloc[1:-1].max()})")

print('\n== 9. Dentro de cada estado no aprobado: código fraude vs legit (¿algún código "de fraude"?) ==')
for st in ['Declined', 'Pending', 'Reversed']:
    d = Q(f"SELECT fraud, coalesce(code,'NULL') code, count(*) n FROM tx WHERE status='{st}' GROUP BY 1,2")
    p = d.pivot(index='fraud', columns='code', values='n').fillna(0).astype(int)
    pp = (p.div(p.sum(axis=1), axis=0) * 100).round(2)
    print(f"-- {st}: code x fraud chi2=%.2f p=%.3f dof=%d V=%.4f" % cramer(p.values))
    print(pd.concat([p, pp.add_suffix('_%')], axis=1).to_string())

print('\n== 10. Robustez del exceso de código 14 en fraudes rechazados ==')
from scipy.stats import chi2 as _chi2
tot = 0; dof = 0
for st in ['Declined', 'Pending', 'Reversed']:
    d = Q(f"SELECT fraud, coalesce(code,'NULL') code, count(*) n FROM tx WHERE status='{st}' GROUP BY 1,2")
    c = cramer(d.pivot(index='fraud', columns='code', values='n').fillna(0).values); tot += c[0]; dof += c[2]
print(f"  chi2 combinado (Declined+Pending+Reversed) = {tot:.2f}, dof={dof}, p={_chi2.sf(tot, dof):.3f}")
print(Q(f"""SELECT {G} g, CASE WHEN year(ts)<=2024 THEN 'a_2023-24' ELSE 'b_2025-26' END periodo,
  count(*) n_decl, sum((code='14')::INT) n14, round(100*avg((code='14')::INT),1) pct14_sobre_codigo
  FROM tx WHERE status='Declined' GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False))
print(Q("""SELECT count(*) n, sum(fraud::INT) f, round(1000*avg(fraud::INT),3) fraude_permil FROM tx WHERE status='Declined' AND code='14'""").to_string(index=False))
