"""Agrupamiento del fraude: por cliente, producto, día, comercio, sucursal, ciudad. Compara contra expectativa binomial/Poisson."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from scipy.stats import binom, poisson
from fraud_00_common import connect, q
pd.set_option('display.width',200)
con = connect()
b = q(con,"SELECT avg(fraud::int) FROM tx").iloc[0,0]
for key in ['customer_id','product_id']:
    d = q(con, f"SELECT n, f, count(*) k FROM (SELECT {key}, count(*) n, sum(fraud::int) f FROM tx GROUP BY 1) GROUP BY 1,2")
    obs = d.groupby('f').k.sum()
    # expectativa: suma sobre grupos de binom(n, b)
    exp = {}
    for fv in range(0,6):
        exp[fv] = float((d.groupby('n').k.sum().reset_index().assign(p=lambda x: binom.pmf(fv, x.n, b)*x.k)).p.sum())
    print(f'\n== fraudes por {key}: observado vs esperado (binomial con tasa global)')
    print(pd.DataFrame({'obs':obs.reindex(range(6)).fillna(0), 'exp':pd.Series(exp)}).round(1).to_string())
# por día
d = q(con,"SELECT ts::date d, count(*) n, sum(fraud::int) f FROM tx GROUP BY 1")
d['e']=d.n*b
disp = ((d.f-d.e)**2/d.e).sum()/(len(d)-1)
print('\n== por día: días', len(d), 'dispersion index (chi2/df)', round(disp,3), 'max f', d.f.max(), 'corr(n,f)', round(np.corrcoef(d.n,d.f)[0,1],3))
d['m']=pd.to_datetime(d.d).dt.to_period('M')
m = d.groupby('m')[['n','f']].sum(); m['rate_pm']=1e3*m.f/m.n
print(m.rate_pm.describe().round(3).to_string())
# comercio
for key in ['merchant_name','branch_id','city','mcat']:
    d = q(con, f"SELECT {key} k, count(*) n, sum(fraud::int) f FROM tx WHERE {key} IS NOT NULL GROUP BY 1")
    d['e']=d.n*b
    disp = ((d.f-d.e)**2/d.e).sum()/(len(d)-1)
    top = d.assign(rr=d.f/d.e).query('n>=5000').sort_values('rr')
    print(f'\n== {key}: grupos {len(d)}, dispersion {disp:.3f}, rr (n>=5000) min {top.rr.min() if len(top) else None} max {top.rr.max() if len(top) else None}')
    if len(top): print(top.tail(3).to_string(index=False)); print(top.head(3).to_string(index=False))
# ¿los fraudes del mismo cliente ocurren cerca en el tiempo?
d = q(con,"""WITH f AS (SELECT customer_id, ts, lag(ts) OVER (PARTITION BY customer_id ORDER BY ts) pts FROM tx WHERE fraud)
SELECT count(*) n_pairs, median(date_diff('day',pts,ts)) med_days, avg(date_diff('day',pts,ts)) avg_days,
 count(*) FILTER (WHERE date_diff('day',pts,ts)<=7) within7 FROM f WHERE pts IS NOT NULL""")
print('\n== gaps entre fraudes consecutivos del mismo cliente'); print(d)
