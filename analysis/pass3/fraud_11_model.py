"""Modelo global de fraude SIN fraud_score (40+ features de tx, producto, cliente y secuenciales). AUC en held-out agrupado por cliente + IC95 bootstrap.
También: modelo restringido a tx con fscore<=30 o nulo (el fraude 'invisible' al score)."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from fraud_00_common import connect, q
con = connect()
df = q(con, """WITH s AS (
SELECT t.transaction_id, t.customer_id, t.fraud, t.fscore, t.amount, t.amount_usd IS NULL no_usd, t.ttype, t.tcat, t.channel, t.currency, t.status, coalesce(t.code,'NA') code,
  coalesce(t.mcat,'NA') mcat, (t.country<>c.country) foreign_c, (t.city=c.city) same_city, t.merchant_name IS NULL no_merch, t.lat IS NULL no_geo, t.branch_id IS NULL no_branch,
  hour(t.ts) hr, dayofweek(t.ts) dow, day(t.ts) dom, month(t.ts) mo, date_diff('day', t.ts::date, t.process_date) plag,
  p.ptype, p.bal, p.credit_limit, p.rate, date_diff('day', p.opened, t.ts::date) prod_age, date_diff('day', t.ts::date, p.expires) to_exp, p.dpd,
  c.segment, c.credit_score, c.income, date_diff('day', c.dob, t.ts::date)/365.25 age, date_diff('day', c.registration_date, t.ts::date) tenure, c.cstatus, c.gender,
  date_diff('second', lag(t.ts) OVER w, t.ts)/3600.0 h_prev, date_diff('second', t.ts, lead(t.ts) OVER w)/3600.0 h_next,
  (lag(t.country) OVER w <> t.country) chg_country, (lag(t.channel) OVER w <> t.channel) chg_channel,
  row_number() OVER w rn, count(*) OVER (PARTITION BY t.customer_id) n_c,
  t.amount / nullif(avg(t.amount) OVER (PARTITION BY t.customer_id),0) amt_ratio,
  row_number() OVER (PARTITION BY t.customer_id, t.merchant_name ORDER BY t.ts) rn_merch,
  count(*) OVER (PARTITION BY t.customer_id, t.ts::date) n_same_day
FROM tx t JOIN pr p USING(product_id) JOIN cu c ON c.customer_id=t.customer_id
WINDOW w AS (PARTITION BY t.customer_id ORDER BY t.ts, t.transaction_id))
SELECT * FROM s WHERE fraud OR hash(transaction_id)%15=0""")
print(df.shape, df.fraud.sum())
cat = ['ttype','tcat','channel','currency','status','code','mcat','ptype','segment','cstatus','gender']
for c in cat: df[c]=df[c].astype('category').cat.codes
for c in df.columns:
    if df[c].dtype==bool or str(df[c].dtype)=='boolean': df[c]=df[c].astype(float)
feats = [c for c in df.columns if c not in ('transaction_id','customer_id','fraud','fscore')]
y = df.fraud.astype(int).values
def run(mask, fs, label):
    X = df.loc[mask, fs].astype(float).values; yy = y[mask]; g = df.loc[mask,'customer_id'].values
    tr, te = next(GroupShuffleSplit(1, test_size=0.3, random_state=0).split(X, yy, g))
    m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=100, random_state=0)
    m.fit(X[tr], yy[tr]); p = m.predict_proba(X[te])[:,1]
    auc = roc_auc_score(yy[te], p); rng=np.random.default_rng(0); bs=[]
    for _ in range(300):
        i = rng.integers(0,len(te),len(te))
        if yy[te][i].sum()>0: bs.append(roc_auc_score(yy[te][i], p[i]))
    print(f"{label}: n_test={len(te)} pos={yy[te].sum()} AUC={auc:.4f} IC95=[{np.percentile(bs,2.5):.4f},{np.percentile(bs,97.5):.4f}]")
run(np.ones(len(df),bool), feats, 'todas las tx, sin fscore')
low = (df.fscore.isna() | (df.fscore<=30)).values
run(low, feats, 'solo fscore<=30 o nulo, sin fscore')
df['fscore_f']=df.fscore.fillna(-1)
run(np.ones(len(df),bool), ['fscore_f'], 'solo fscore (nulo=-1)')
run(np.ones(len(df),bool), feats+['fscore_f'], 'fscore + todas')
