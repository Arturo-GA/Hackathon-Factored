# Consolidacion: (a) n_tx ~ 13 x productos activos (R2); (b) AUC motivo Transaccional/Queja desde recencia de tx (held-out por cliente, IC95 bootstrap)
import duckdb, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
d = q("""select c.customer_id, coalesce(t.n,0) n_tx, coalesce(r.nact,0) nact, coalesce(k.n,0) n_cc
  from cu c left join (select customer_id, count(*) n from tx group by 1) t using(customer_id)
  left join (select customer_id, sum((pstatus='Active')::int) nact from pr group by 1) r using(customer_id)
  left join (select customer_id, count(*) n from cc group by 1) k using(customer_id)""")
pred = 13.016*d.nact
print('R2 n_tx ~ 13*nact:', round(1-((d.n_tx-pred)**2).sum()/((d.n_tx-d.n_tx.mean())**2).sum(),4))
print('clientes sin activos:', (d.nact==0).sum(), 'con tx:', ((d.nact==0)&(d.n_tx>0)).sum())
r = d.n_tx/d.nact.replace(0,np.nan); print('n_tx/nact mean', round(r.mean(),2))
print('R2 n_cc ~ n_tx:', round(np.corrcoef(d.n_cc, d.n_tx)[0,1]**2,5))
# (b) motivo desde recencia
con.execute("create temp table c as select interaction_id, customer_id, ts, cat from cc where hash(customer_id)%4=0")
con.execute("create temp table t as select customer_id, ts, status, fraud from tx where customer_id in (select customer_id from c)")
f = q("""select c.customer_id, c.cat,
   (select date_diff('hour', max(t.ts), c.ts) from t where t.customer_id=c.customer_id and t.ts<=c.ts) h_last,
   (select date_diff('hour', max(t.ts), c.ts) from t where t.customer_id=c.customer_id and t.ts<=c.ts and t.status='Declined') h_dec,
   (select count(*) from t where t.customer_id=c.customer_id and t.ts between c.ts - interval 30 day and c.ts) n30,
   (select count(*) from t where t.customer_id=c.customer_id and t.ts between c.ts - interval 30 day and c.ts and t.status<>'Approved') nna30
   from (select * from c using sample 120000) c""")
X = pd.DataFrame({'h_last': np.log1p(f.h_last.fillna(1e5)), 'no_tx': f.h_last.isna().astype(int), 'h_dec': np.log1p(f.h_dec.fillna(1e5)),
                  'n30': f.n30, 'nna30': f.nna30})
cust = f.customer_id.values
rng = np.random.default_rng(0)
test = np.isin(cust, pd.unique(cust)[rng.random(len(pd.unique(cust)))<0.3])
for tgt in ['Transaccional','Queja']:
    y = (f.cat==tgt).astype(int).values
    m = LogisticRegression(max_iter=500).fit(X[~test], y[~test])
    p = m.predict_proba(X[test])[:,1]; yt = y[test]
    a = roc_auc_score(yt, p)
    bs = []
    idx = np.arange(len(yt))
    for _ in range(200):
        s = rng.choice(idx, len(idx)); bs.append(roc_auc_score(yt[s], p[s]))
    print(tgt, 'n_test', len(yt), 'AUC', round(a,4), 'IC95', np.round(np.percentile(bs,[2.5,97.5]),4))
