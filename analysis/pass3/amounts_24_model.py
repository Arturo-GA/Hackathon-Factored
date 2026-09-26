import duckdb, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import r2_score
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
df=con.execute("""select t.customer_id, t.ttype, t.channel, t.status, coalesce(t.code,'NA') code, t.country, t.currency, hour(t.ts) h, dayofweek(t.ts) dow, month(t.ts) m,
 t.fscore, t.fraud::int fraud, coalesce(t.mcat,'NA') mcat, cu.segment, cu.income/(case cu.country when 'Argentina' then 350 when 'Colombia' then 4000 else 17 end) inc_usd, cu.credit_score, cu.cstatus,
 p.ptype, p.bal/(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) bal_usd, p.credit_limit/(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) lim_usd, p.dpd,
 t.amount/(case t.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) a
 from (select * from tx using sample 250000 rows) t join cu using(customer_id) join pr p using(product_id)""").df()
lo={'Purchase':5,'Withdrawal':20,'Transfer':100,'Payment':50,'Deposit':50,'Adjustment':10}
hi={'Purchase':500,'Withdrawal':500,'Transfer':10000,'Payment':2000,'Deposit':5000,'Adjustment':1000}
df['u']=(df.a-df.ttype.map(lo))/(df.ttype.map(hi)-df.ttype.map(lo))
df['la']=np.log(df.a)
cats=['ttype','channel','status','code','country','currency','mcat','segment','cstatus','ptype']
for c in cats: df[c]=df[c].astype('category').cat.codes
feats=[c for c in df.columns if c not in ('customer_id','a','u','la')]
gss=GroupShuffleSplit(n_splits=1,test_size=0.3,random_state=0)
tr,te=next(gss.split(df,groups=df.customer_id))
X=df[feats]; 
catmask=[c in cats for c in feats]
for target,fs in [('la',['ttype']),('la',feats),('u',[f for f in feats if f!='ttype'])]:
    m=HistGradientBoostingRegressor(max_iter=200,learning_rate=0.1,categorical_features=[c in cats for c in fs],random_state=0)
    m.fit(df.iloc[tr][fs],df.iloc[tr][target])
    p=m.predict(df.iloc[te][fs])
    y=df.iloc[te][target].values
    r=r2_score(y,p)
    # bootstrap CI
    rng=np.random.default_rng(0); bs=[]
    for _ in range(200):
        i=rng.integers(0,len(y),len(y)); bs.append(r2_score(y[i],p[i]))
    print(target, 'features:', 'ttype only' if fs==['ttype'] else f'{len(fs)} feats', 'R2=%.4f IC95=[%.4f, %.4f]'%(r,np.percentile(bs,2.5),np.percentile(bs,97.5)))
