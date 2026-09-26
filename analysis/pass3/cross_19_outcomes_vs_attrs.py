# H14: fraude / rechazo / codigo vs atributos de producto y cliente (tablas pr, cu) y digitales (de) - AUC univariada
import duckdb, numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
# todas las fraudes + muestra de no fraude; todas las declined via muestra
df = con.execute("""
 with base as (
   select * from tx where fraud
   union all select * from (select * from tx where not fraud using sample 150000))
 select b.fraud::int fraud, (b.status='Declined')::int declined, b.code, b.status, b.customer_id,
   p.bal, p.credit_limit, p.rate, p.dpd, date_diff('day', p.opened, cast(b.ts as date)) prod_age, date_diff('day', cast(b.ts as date), p.expires) days_to_exp,
   p.app::int app, p.opening_channel, p.ptype,
   c.credit_score, c.income, date_diff('year', c.dob, cast(b.ts as date)) age, date_diff('day', cast(c.registration_date as date), cast(b.ts as date)) tenure,
   c.segment, c.gender, c.cstatus, c.mkt::int mkt, c.education_level, c.occupation,
   (select count(*) from pr p2 where p2.customer_id=b.customer_id) n_prod
 from base b join pr p using(product_id) join cu c on c.customer_id=b.customer_id""").fetchdf()
print(df.shape, df.fraud.sum(), df.declined.sum())
num = ['bal','credit_limit','rate','dpd','prod_age','days_to_exp','app','credit_score','income','age','tenure','mkt','n_prod']
cat = ['opening_channel','ptype','segment','gender','cstatus','education_level','occupation']
def auc(y, x):
    m = ~pd.isna(x)
    if m.sum()<100 or y[m].nunique()<2: return np.nan
    a = roc_auc_score(y[m], x[m]); return max(a,1-a)
for tgt in ['fraud','declined']:
    y = df[tgt]
    res = {c: auc(y, df[c]) for c in num}
    for c in cat:
        te = df.groupby(c)[tgt].mean(); res[c] = auc(y, df[c].map(te))
    print(tgt, {k: round(v,3) for k,v in sorted(res.items(), key=lambda kv: -np.nan_to_num(kv[1]))})
# codes among declined vs attrs
d = df[df.status=='Declined'].copy()
for code in ['05','14','51','54']:
    y = (d.code==code).astype(int)
    res = {c: auc(y, d[c]) for c in num}
    print('code',code, int(y.sum()), {k: round(v,3) for k,v in sorted(res.items(), key=lambda kv: -np.nan_to_num(kv[1]))[:5]})
