import duckdb, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import r2_score
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: con.execute(s).df()
K="(case t.currency when 'ARS' then 350.0 when 'COP' then 4000.0 else 1.0 end)"
PK="(case p.currency when 'ARS' then 350.0 when 'COP' then 4000.0 else 1.0 end)"
# duplicados de monto dentro de cliente (reembolsos/reintentos)
print(q("""select count(*) n_pairs, sum((a.ttype<>b.ttype)::int) cross_type from tx a join tx b on a.customer_id=b.customer_id and a.amount=b.amount and a.transaction_id<b.transaction_id""").to_string())
# chance expectation approx: sum over customers of pairs * P(same amount)
# declines by raw USD-eq quintile
print(q(f"""with z as (select t.*, ntile(5) over (order by t.amount/{K}) qq from tx t) select qq, round(avg((status='Declined')::int)*100,2) decl, round(avg((code='51')::int)*100,2) c51, round(avg(case when status='Declined' then (code='51')::int end)*100,2) c51_in_decl, round(avg(fraud::int)*1000,3) fr from z group by 1 order by 1""").to_string())
df=q(f"""select t.customer_id, t.ttype, t.tcat, t.channel, t.status, coalesce(t.code,'NA') code, t.country, t.currency, coalesce(t.mcat,'NA') mcat,
 hour(t.ts) h, dayofweek(t.ts) dow, month(t.ts) m, year(t.ts) y, t.fscore, t.fraud::int fraud, cu.segment, cu.income, cu.credit_score, cu.cstatus, cu.occupation,
 p.ptype, p.bal/{PK} bal, p.credit_limit/{PK} lim, p.dpd, p.rate, t.amount/{K} a
 from (select * from tx using sample 250000 rows (reservoir, 7)) t join cu using(customer_id) join pr p using(product_id)""")
lo={'Purchase':5,'Withdrawal':20,'Transfer':100,'Payment':50,'Deposit':50,'Adjustment':10}
hi={'Purchase':500,'Withdrawal':500,'Transfer':10000,'Payment':2000,'Deposit':5000,'Adjustment':1000}
df['u']=(df.a-df.ttype.map(lo))/(df.ttype.map(hi)-df.ttype.map(lo)); df['la']=np.log(df.a)
cats=['ttype','tcat','channel','status','code','country','currency','mcat','segment','cstatus','occupation','ptype']
for c in cats: df[c]=df[c].astype('category').cat.codes
feats=[c for c in df.columns if c not in ('customer_id','a','u','la')]
tr,te=next(GroupShuffleSplit(1,test_size=0.3,random_state=1).split(df,groups=df.customer_id))
def fit(target,fs):
    m=HistGradientBoostingRegressor(max_iter=300,learning_rate=0.05,categorical_features=[c in cats for c in fs],random_state=0)
    m.fit(df.iloc[tr][fs],df.iloc[tr][target]); p=m.predict(df.iloc[te][fs]); y=df.iloc[te][target].values
    g=df.iloc[te].customer_id.values; ug=np.unique(g); idx={c:np.where(g==c)[0] for c in []}
    rng=np.random.default_rng(0); bs=[]
    # bootstrap agrupado por cliente
    codes=pd.factorize(g)[0]; order=np.argsort(codes); starts=np.searchsorted(codes[order],np.arange(codes.max()+1))
    ends=np.append(starts[1:],len(codes))
    for _ in range(200):
        s=rng.integers(0,len(starts),len(starts))
        ii=np.concatenate([order[starts[k]:ends[k]] for k in s])
        bs.append(r2_score(y[ii],p[ii]))
    print(target,len(fs),'feats','R2=%.4f IC95=[%.4f,%.4f]'%(r2_score(y,p),*np.percentile(bs,[2.5,97.5])))
fit('la',['ttype']); fit('la',['ttype','currency']); fit('la',feats); fit('u',[f for f in feats if f!='ttype'])
