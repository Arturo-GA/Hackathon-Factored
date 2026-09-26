"""Verificador escéptico (reintento): fraud_autorizacion_ignora_score.
A. Reproducción: estado por grupo (legit / fraude fscore>30 / fraude bajo-nulo), RR con IC95 (Wald y bootstrap por cliente).
B. Código dentro de no-Approved: fraude vs legit.
C. ¿El estado es independiente de TODO? (V de Cramér con ttype, canal, país, moneda, año, decil de monto, ptype, segmento).
D. fscore -> estado: AUC en legítimas (rango exacto en SQL) y dentro del fraude (bootstrap por cliente).
E. Reacción del banco tras el fraude: Adjustment / reembolso del mismo monto / rechazos en el mismo producto a 30 días.
F. Tasa mensual de fraude_hi aprobado; G. concentración del fraude por cliente."""
import sys; sys.path.insert(0, 'analysis/pass3')
import numpy as np, pandas as pd
from scipy.stats import chi2_contingency
from sklearn.metrics import roc_auc_score
from fraud_00_common import connect, q
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = connect()

def rr_ci(a, n1, b, n0):
    r = (a/n1)/(b/n0); se = np.sqrt(1/a - 1/n1 + 1/b - 1/n0)
    return r, np.exp(np.log(r)-1.96*se), np.exp(np.log(r)+1.96*se)

def cramer(ct):
    ct = np.asarray(ct, float); ct = ct[ct.sum(1) > 0][:, ct.sum(0) > 0]
    chi2, p, dof, _ = chi2_contingency(ct, correction=False)
    return chi2, p, np.sqrt(chi2/(ct.sum()*(min(ct.shape)-1)))

G = "CASE WHEN NOT fraud THEN 'legit' WHEN fscore>30 THEN 'fraud_hi' ELSE 'fraud_lo_null' END"
print('== A. Estado por grupo ==')
d = q(con, f"SELECT {G} g, status, count(*) n FROM tx GROUP BY ALL")
pv = d.pivot(index='g', columns='status', values='n').fillna(0).astype(int)
pv.loc['fraud_all'] = pv.loc['fraud_hi'] + pv.loc['fraud_lo_null']; pv['N'] = pv.sum(1)
print(pv.assign(**{f'%{s}': (100*pv[s]/pv.N).round(3) for s in ['Approved', 'Declined', 'Pending', 'Reversed']}).to_string())
for s in ['Approved', 'Declined', 'Pending', 'Reversed']:
    for g in ['fraud_hi', 'fraud_all']:
        r, lo, hi = rr_ci(pv.loc[g, s], pv.loc[g, 'N'], pv.loc['legit', s], pv.loc['legit', 'N'])
        print(f'  {s:9s} {g:9s} RR={r:.3f} IC95[{lo:.3f},{hi:.3f}]')
print('  status x fraud: chi2=%.2f p=%.3f V=%.5f' % cramer(pv.loc[['legit', 'fraud_all'], ['Approved', 'Declined', 'Pending', 'Reversed']].values))
# bootstrap por cliente de la tasa de Declined en fraude (clustering)
f = q(con, "SELECT customer_id, fscore, status FROM tx WHERE fraud")
print(f'  fraudes={len(f)} clientes distintos={f.customer_id.nunique()} max por cliente={f.customer_id.value_counts().max()}')
p_leg = pv.loc['legit', 'Declined']/pv.loc['legit', 'N']
cust = pd.factorize(f.customer_id)[0]; y = (f.status == 'Declined').values.astype(float); nc = cust.max()+1
rng = np.random.default_rng(7); rrs = []
for _ in range(2000):
    w = np.bincount(rng.integers(0, nc, nc), minlength=nc)[cust]
    rrs.append((w*y).sum()/w.sum()/p_leg)
print(f'  RR Declined fraude/legit bootstrap por cliente IC95 [{np.percentile(rrs,2.5):.3f}, {np.percentile(rrs,97.5):.3f}]')

print('\n== B. Código dentro de no-Approved (fraude vs legit) y código de Approved ==')
d = q(con, "SELECT fraud, status='Approved' ap, coalesce(code,'NULL') code, count(*) n FROM tx GROUP BY ALL")
for ap in [False, True]:
    t = d[d.ap == ap].pivot(index='fraud', columns='code', values='n').fillna(0).astype(int)
    print(('Approved' if ap else 'no-Approved'), (t.div(t.sum(1), axis=0)*100).round(2).assign(N=t.sum(1)).to_string())
    print('   code x fraud: chi2=%.2f p=%.3f V=%.5f' % cramer(t.values))

print('\n== C. ¿Estado independiente de todo? V de Cramér status x variable ==')
con.execute("CREATE TEMP TABLE t AS SELECT t.status, t.ttype, t.channel, t.country, t.currency, year(t.ts) yr, "
            "ntile(10) OVER (PARTITION BY t.currency ORDER BY t.amount) amt10, p.ptype, c.segment, "
            "CASE WHEN t.fscore IS NULL THEN 'nulo' ELSE 'score' END fs_null "
            "FROM tx t LEFT JOIN pr p USING(product_id) LEFT JOIN cu c ON c.customer_id=t.customer_id")
for v in ['ttype', 'channel', 'country', 'currency', 'yr', 'amt10', 'ptype', 'segment', 'fs_null']:
    d = q(con, f"SELECT status, coalesce({v}::VARCHAR,'NA') v, count(*) n FROM t GROUP BY ALL")
    ct = d.pivot(index='status', columns='v', values='n').fillna(0)
    rates = (100*ct.loc['Declined']/ct.sum(0))
    print(f'  {v:8s}: V={cramer(ct.values)[2]:.5f} p={cramer(ct.values)[1]:.3f}  %Declined rango [{rates.min():.2f}, {rates.max():.2f}] ({ct.shape[1]} niveles)')

print('\n== D. fscore -> estado ==')
for tgt in ["status='Declined'", "status<>'Approved'"]:
    a = q(con, f"""WITH s AS (SELECT fscore, ({tgt}) y FROM tx WHERE NOT fraud AND fscore IS NOT NULL),
      r AS (SELECT y, rank() OVER (ORDER BY fscore) rk FROM s)
      SELECT (sum(rk) FILTER (WHERE y) - count(*) FILTER (WHERE y)*(count(*) FILTER (WHERE y)+1)/2.0)
       / (count(*) FILTER (WHERE y)::DOUBLE * count(*) FILTER (WHERE NOT y)) auc, count(*) FILTER (WHERE y) npos, count(*) n FROM r""")
    auc, n1, n = a.auc[0], a.npos[0], a.n[0]; n0 = n-n1
    se = np.sqrt((auc*(1-auc) + (n1-1)*(auc/(2-auc)-auc**2) + (n0-1)*(2*auc**2/(1+auc)-auc**2))/(n1*n0))
    print(f'  legit, AUC fscore -> {tgt}: {auc:.4f} IC95 [{auc-1.96*se:.4f}, {auc+1.96*se:.4f}] (npos={n1:,}, n={n:,})')
fs = f[f.fscore.notna()].reset_index(drop=True); cs = pd.factorize(fs.customer_id)[0]; ncs = cs.max()+1
for name, yy in [('Declined', (fs.status == 'Declined').values), ('no-Approved', (fs.status != 'Approved').values)]:
    auc = roc_auc_score(yy, fs.fscore.values); bs = []
    for _ in range(1000):
        w = np.bincount(rng.integers(0, ncs, ncs), minlength=ncs)[cs]
        bs.append(roc_auc_score(yy, fs.fscore.values, sample_weight=w))
    print(f'  fraude con score (n={len(fs)}, pos={yy.sum()}): AUC fscore -> {name} = {auc:.3f} IC95 boot cliente [{np.percentile(bs,2.5):.3f}, {np.percentile(bs,97.5):.3f}]')

print('\n== E. Reacción del banco en el mismo producto, 30 días tras el evento (fraude vs muestra de legítimas) ==')
con.execute("""CREATE TEMP TABLE ev AS SELECT transaction_id eid, product_id, ts ev_ts, amount ev_amt, fraud ev_fraud,
   fraud AND fscore>30 ev_hi, status ev_status FROM tx WHERE fraud OR hash(transaction_id) % 100 = 0""")
d = q(con, """SELECT e.ev_fraud, count(DISTINCT e.eid) n_ev, count(s.transaction_id) n_post,
   sum((s.status='Declined')::int) post_decl, sum((s.status<>'Approved')::int) post_noap,
   count(DISTINCT CASE WHEN s.ttype='Adjustment' THEN e.eid END) ev_con_adj,
   count(DISTINCT CASE WHEN s.ttype IN ('Adjustment','Deposit') AND abs(s.amount-e.ev_amt) < 0.01 THEN e.eid END) ev_reemb_mismo_monto,
   count(DISTINCT CASE WHEN s.transaction_id IS NOT NULL THEN e.eid END) ev_con_post
   FROM ev e LEFT JOIN tx s ON s.product_id=e.product_id AND s.ts > e.ev_ts AND s.ts <= e.ev_ts + INTERVAL 30 DAY AND s.transaction_id<>e.eid
   GROUP BY 1 ORDER BY 1""").set_index('ev_fraud')
print(d.to_string())
for num, den in [('post_decl', 'n_post'), ('post_noap', 'n_post'), ('ev_con_adj', 'n_ev'), ('ev_con_post', 'n_ev')]:
    r, lo, hi = rr_ci(d.loc[True, num], d.loc[True, den], d.loc[False, num], d.loc[False, den])
    print(f'  {num}/{den}: fraude {100*d.loc[True,num]/d.loc[True,den]:.2f}% vs legit {100*d.loc[False,num]/d.loc[False,den]:.2f}%  RR={r:.3f} [{lo:.3f},{hi:.3f}]')
print(q(con, "SELECT ev_fraud, ev_status, count(*) n FROM ev WHERE ev_fraud GROUP BY ALL ORDER BY 2").to_string(index=False))

print('\n== F. Tasa mensual de fraude fscore>30 ==')
print(q(con, """SELECT date_diff('day', min(ts)::DATE, max(ts)::DATE)/30.4375 meses,
  count(*) FILTER (WHERE fraud AND fscore>30) hi_total, count(*) FILTER (WHERE fraud AND fscore>30 AND status='Approved') hi_aprob,
  count(*) FILTER (WHERE fraud) fraude_total, count(*) FILTER (WHERE NOT fraud AND fscore>30) legit_gt30 FROM tx""").assign(
  hi_mes=lambda x: x.hi_total/x.meses, hi_aprob_mes=lambda x: x.hi_aprob/x.meses).round(2).to_string(index=False))
