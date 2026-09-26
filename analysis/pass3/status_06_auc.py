"""H9: AUC de Declined (y de cada codigo) con features de fila + historial cliente/producto + tablas pr/cu.
Held-out agrupado por cliente, IC95 bootstrap."""
import duckdb, numpy as np, pandas as pd, warnings
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import roc_auc_score
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
df = con.execute("""
with h as (
 select transaction_id, customer_id, product_id, ts, ttype, channel, currency, country, amount, amount_usd, status, code, fscore, fraud,
  merchant_name, mcat, branch_id, lat,
  count(*) over wc - 1 c_prev_n,
  coalesce(sum(case when status='Declined' then 1 else 0 end) over (partition by customer_id order by ts rows between unbounded preceding and 1 preceding),0) c_prev_decl,
  coalesce(sum(case when status<>'Approved' then 1 else 0 end) over (partition by customer_id order by ts rows between unbounded preceding and 1 preceding),0) c_prev_bad,
  lag(status) over wc prev_status,
  lag(code) over wc prev_code,
  date_diff('minute', lag(ts) over wc, ts) mins_since_prev,
  avg(amount) over (partition by customer_id order by ts rows between unbounded preceding and 1 preceding) c_prev_avg_amt,
  coalesce(sum(case when status='Declined' then 1 else 0 end) over (partition by product_id order by ts rows between unbounded preceding and 1 preceding),0) p_prev_decl,
  count(*) over (partition by product_id order by ts rows between unbounded preceding and 1 preceding) p_prev_n,
  count(*) over (partition by customer_id order by ts range between interval 1 day preceding and current row) c_vel24
 from tx window wc as (partition by customer_id order by ts rows between unbounded preceding and current row)
), hs as (select * from h using sample 280000 rows (reservoir, 42))
select h.*, p.ptype, p.bal, p.credit_limit, p.rate, p.pstatus, p.dpd, p.app, p.opening_channel,
  date_diff('day', p.opened, h.ts) prod_age, date_diff('day', h.ts, p.expires) days_to_exp,
  u.segment, u.credit_score, u.income, u.cstatus, u.country cu_country, date_diff('day', u.registration_date, h.ts) cu_tenure,
  year(h.ts)-year(u.dob) age, u.gender, u.occupation
from hs h
left join pr p on p.product_id=h.product_id left join cu u on u.customer_id=h.customer_id
""").fetchdf()
print(df.shape, df.status.value_counts(normalize=True).round(4).to_dict())
df['hour']=df.ts.dt.hour; df['dow']=df.ts.dt.dayofweek; df['month']=df.ts.dt.month; df['year']=df.ts.dt.year
df['amt_ratio']=df.amount/df.c_prev_avg_amt
df['c_prev_decl_rate']=df.c_prev_decl/df.c_prev_n.replace(0,np.nan)
df['amt_gt_bal']=(df.amount>df.bal).astype(float)
df['amt_vs_lim']=df.amount/df.credit_limit
df['expired']=(df.days_to_exp<0).astype(float)
df['foreign']=(df.country!=df.cu_country).astype(float)
df['merch_null']=df.merchant_name.isna().astype(float); df['lat_null']=df.lat.isna().astype(float)
cat=['ttype','channel','currency','country','mcat','prev_status','prev_code','ptype','pstatus','app','opening_channel','segment','cstatus','gender','occupation','merchant_name']
num=['amount','amount_usd','fscore','c_prev_n','c_prev_decl','c_prev_bad','mins_since_prev','c_prev_avg_amt','p_prev_decl','p_prev_n','c_vel24',
     'bal','credit_limit','rate','dpd','prod_age','days_to_exp','credit_score','income','cu_tenure','age','hour','dow','month','year',
     'amt_ratio','c_prev_decl_rate','amt_gt_bal','amt_vs_lim','expired','foreign','merch_null','lat_null']
X = pd.DataFrame({c: df[c] for c in num})
for c in cat: X[c]=df[c].astype('category').cat.codes
catmask=[False]*len(num)+[True]*len(cat)
def fit_auc(y, mask=None, label=''):
    Xs, ys, g = (X, y, df.customer_id) if mask is None else (X[mask], y[mask], df.customer_id[mask])
    tr, te = next(GroupShuffleSplit(1, test_size=0.3, random_state=0).split(Xs, ys, g))
    m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=31, categorical_features=catmask, random_state=0)
    m.fit(Xs.iloc[tr], ys.iloc[tr]); p = m.predict_proba(Xs.iloc[te])[:,1]; yt = ys.iloc[te].values
    auc = roc_auc_score(yt, p); rng=np.random.default_rng(0); bs=[]
    for _ in range(200):
        i = rng.integers(0,len(yt),len(yt))
        if yt[i].min()!=yt[i].max(): bs.append(roc_auc_score(yt[i], p[i]))
    print(f"{label:30s} n_test={len(yt):6d} pos={yt.mean():.4f} AUC={auc:.4f} IC95=[{np.quantile(bs,0.025):.4f},{np.quantile(bs,0.975):.4f}]")
fit_auc((df.status=='Declined').astype(int), label='Declined vs resto')
fit_auc((df.status!='Approved').astype(int), label='No aprobada vs Approved')
fit_auc((df.status=='Reversed').astype(int), label='Reversed vs resto')
fit_auc((df.status=='Pending').astype(int), label='Pending vs resto')
dm = (df.status!='Approved') & df.code.notna()
for c in ['05','14','51','54']:
    fit_auc((df.code==c).astype(int), mask=dm, label=f'code {c} | no aprobada')
fit_auc(df.code.isna().astype(int), label='code nulo')
