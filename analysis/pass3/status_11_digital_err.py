"""Eventos digitales (Error/Transaction, FormSubmit, Login) alrededor de tx App/Web segun estado; uniformidad de montos (KS)."""
import duckdb, pandas as pd, numpy as np, warnings
from scipy.stats import kstest
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
for et, cat in [('Error','Transaction'),('FormSubmit','Transaction'),('Login','Authentication')]:
    r = q(f"""with t as (select transaction_id, customer_id, ts, status from tx where channel in ('App','Web')),
     e as (select customer_id, ts ets from de where event_type='{et}' and event_category='{cat}' and customer_id is not null),
     m as (select distinct t.transaction_id from t join e on e.customer_id=t.customer_id and e.ets between t.ts - interval 1 hour and t.ts + interval 1 hour)
    select t.status, count(*) n, count(m.transaction_id) con_evento, count(m.transaction_id)/count(*) tasa
    from t left join m using(transaction_id) group by 1 order by 1""")
    print(et, cat); print(r.to_string())
# sesiones digitales el mismo dia
r = q("""with t as (select transaction_id, customer_id, cast(ts as date) d, status, channel from tx),
 e as (select distinct customer_id, cast(ts as date) d from de where customer_id is not null),
 m as (select t.transaction_id from t join e using(customer_id, d))
 select channel, status, count(*) n, count(m.transaction_id)/count(*) tasa_evento_mismo_dia from t left join m using(transaction_id) group by 1,2 order by 1,2""")
print(r.pivot(index='channel',columns='status',values='tasa_evento_mismo_dia').round(4).to_string())
# KS uniforme en USD
caps = {'Purchase':(5,500),'Withdrawal':(20,500),'Payment':(50,2000),'Deposit':(50,5000),'Transfer':(100,10000),'Adjustment':(10,1000)}
for tt,(a,b) in caps.items():
    x = q(f"select coalesce(amount_usd, amount) v from tx where ttype='{tt}' and (currency='USD' or amount_usd is not null) using sample 50000 rows").v.values
    x = x[~np.isnan(x)]
    print(tt, len(x), 'min',x.min().round(2),'max',x.max().round(2), 'KS vs U(%s,%s) D=%.4f p=%.3f'%(a,b,*kstest(x,'uniform',args=(a,b-a))))
