# Parte F: GBM con features extra (tcat, comercio, ciudad, sucursal, lat/lon, minuto/segundo, rezago, u previa, brecha, estado previo, cliente, producto)
# objetivo u (posición en el rango de su ttype); held-out agrupado por cliente; IC95 bootstrap por cliente
import duckdb, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import r2_score
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
K="(case t.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"
LO="(case t.ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Transfer' then 100 when 'Payment' then 50 when 'Deposit' then 50 else 10 end)"
HI="(case t.ttype when 'Purchase' then 500 when 'Withdrawal' then 500 when 'Transfer' then 10000 when 'Payment' then 2000 when 'Deposit' then 5000 else 1000 end)"
df=con.execute(f"""with s as (select t.*, (t.amount/{K} - {LO})/({HI}-{LO}) u from tx t where hash(product_id) % 12 = 0),
 w as (select *, lag(u) over x pu, lag(ttype) over x pt, lag(status) over x pst, epoch(ts)-epoch(lag(ts) over x) gap,
   count(*) over (partition by product_id) nprod from s window x as (partition by product_id order by ts, transaction_id))
 select w.customer_id, w.u, w.ttype, w.currency, w.channel, w.status, coalesce(w.code,'NA') code, w.fraud::int fraud, w.fscore, w.country, coalesce(w.country_raw,'NA') country_raw,
  coalesce(w.city,'NA') city, coalesce(w.tcat,'NA') tcat, coalesce(w.mcat,'NA') mcat, coalesce(w.merchant_name,'NA') merchant, w.branch_id, w.lat, w.lon,
  hour(w.ts) h, minute(w.ts) mi, second(w.ts) se, dayofweek(w.ts) dow, day(w.ts) dom, month(w.ts) mo, year(w.ts) yr, datediff('day', cast(w.ts as date), w.process_date) lagd,
  w.pu, coalesce(w.pt,'NA') pt, coalesce(w.pst,'NA') pst, w.gap, w.nprod,
  cu.segment, cu.income, cu.credit_score, year(cu.dob) byear, cu.cstatus, p.ptype, p.bal, p.credit_limit, p.rate, p.dpd
 from w left join cu using(customer_id) left join pr p using(product_id)""").df()
print('filas', len(df), 'clientes', df.customer_id.nunique(), flush=True)
cats=['ttype','currency','channel','status','code','country','country_raw','city','tcat','mcat','merchant','pt','pst','segment','cstatus','ptype']
for c in cats: df[c]=df[c].astype('category').cat.codes
df['branch_id']=df.branch_id.astype('category').cat.codes  # ordinal (350 niveles)
feats=[c for c in df.columns if c not in ('customer_id','u')]
gss=GroupShuffleSplit(n_splits=1,test_size=0.3,random_state=1)
tr,te=next(gss.split(df,groups=df.customer_id))
y=df.u.values; cid=df.customer_id.astype('category').cat.codes.values
for name,fs in [('todas (%d)'%len(feats),feats),('sin ttype',[f for f in feats if f!='ttype'])]:
    m=HistGradientBoostingRegressor(max_iter=300,learning_rate=0.05,max_leaf_nodes=31,categorical_features=[c in cats for c in fs],random_state=0,early_stopping=True,validation_fraction=0.15)
    m.fit(df.iloc[tr][fs],y[tr]); p=m.predict(df.iloc[te][fs]); yt=y[te]; ct=cid[te]
    r=r2_score(yt,p)
    uc,inv=np.unique(ct,return_inverse=True); rng=np.random.default_rng(0); bs=[]
    for _ in range(200):
        pick=rng.integers(0,len(uc),len(uc)); w=np.bincount(pick,minlength=len(uc))[inv]; idx=np.repeat(np.arange(len(yt)),w)
        bs.append(r2_score(yt[idx],p[idx]))
    print(f"u ~ {name}: R2 held-out={r:.5f} IC95=[{np.percentile(bs,2.5):.5f}, {np.percentile(bs,97.5):.5f}] iter={m.n_iter_}", flush=True)
print('corr(u, u_previa mismo producto)=%.4f  n=%d' % (df[['u','pu']].dropna().corr().iloc[0,1], df.pu.notna().sum()))
