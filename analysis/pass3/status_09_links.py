"""Vinculos ocultos: reclamos (claimed) y eventos digitales (event_value, Error) vs transacciones del cliente."""
import duckdb, pandas as pd, warnings, time
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width',250); pd.set_option('display.max_colwidth',80)
t0=time.time()
print(q("select category, subcategory, count(*) n, avg(claimed) avg_claimed, avg(case when claimed is null then 1 else 0 end) claimed_null from cp group by 1,2 order by 1,3 desc").to_string())
print(q("select description from cp where category='Transactions' using sample 6 rows").to_string())
# claimed vs montos de tx del mismo cliente
print(q("""with c as (select complaint_id, customer_id, claimed, currency, ts from cp where claimed is not null)
select count(distinct c.complaint_id) n_match_exact_cli from c join tx t on t.customer_id=c.customer_id and t.amount=c.claimed""").to_string())
print(q("""with c as (select complaint_id, customer_id, claimed, currency, ts from cp where claimed is not null)
select count(distinct c.complaint_id) n_match_1pct_90d from c join tx t on t.customer_id=c.customer_id and abs(t.amount-c.claimed)<=0.01*c.claimed
 and t.ts between c.ts - interval 90 day and c.ts""").to_string())
print(q("select count(*) n, min(claimed), median(claimed), max(claimed) from cp where claimed is not null").to_string())
print(q("select currency, count(*) from cp group by 1").to_string())
print(f"{time.time()-t0:.0f}s")
# eventos digitales con event_value vs tx
print(q("""with e as (select event_id, customer_id, ts, event_value, event_type from de where event_type in ('Purchase','FormSubmit') and event_value is not null and customer_id is not null using sample 30000 rows)
select e.event_type, count(distinct e.event_id) n_match from e join tx t on t.customer_id=e.customer_id and abs(t.amount-e.event_value)<=0.01*e.event_value
 and t.ts between e.ts - interval 1 day and e.ts + interval 1 day group by 1""").to_string())
print(q("""select event_type, count(*) n, min(event_value), median(event_value), max(event_value) from de where event_value is not null group by 1""").to_string())
print(f"{time.time()-t0:.0f}s")
# Error digitales cerca de Declined en App/Web
print(q("""with t as (select transaction_id, customer_id, ts, status from tx where channel in ('App','Web') using sample 200000 rows),
 e as (select customer_id, ts from de where event_type='Error' and event_category='Transaction' and customer_id is not null)
select t.status, count(*) n, avg(case when ex then 1 else 0 end) err_1h from (
 select t.transaction_id, t.status, exists(select 1 from e where e.customer_id=t.customer_id and e.ts between t.ts - interval 1 hour and t.ts + interval 1 hour) ex from t) t group by 1""").to_string())
print(f"{time.time()-t0:.0f}s")
