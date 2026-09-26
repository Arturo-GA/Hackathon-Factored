import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
q("select event_type, count(*) n, min(event_value), median(event_value), max(event_value), avg((event_value=floor(event_value))::int) whole from de where event_value is not null group by all")
con.execute("create temp table e as select event_id, customer_id, event_value v, ts, event_type from de where event_value is not null and customer_id is not null using sample 30000 rows")
q("select event_type, count(*) n from e group by 1")
q("""select e.event_type, count(distinct e.event_id) nmatch_raw from e join tx t on t.customer_id=e.customer_id and abs(t.amount - e.v)<0.005 group by e.event_type""")
q("""select e.event_type, count(distinct e.event_id) nmatch_usdeq from e join tx t on t.customer_id=e.customer_id and abs(t.amount/(case t.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) - e.v)<0.01 group by e.event_type""")
# same customer, tx within +-1 day, amount within 1%
q("""select e.event_type, count(distinct e.event_id) nmatch_time from e join tx t on t.customer_id=e.customer_id and abs(epoch(t.ts)-epoch(e.ts))<86400
 and abs(t.amount/(case t.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)/e.v-1)<0.01 group by e.event_type""")
q("""with d as (select customer_id, count(*) filter (where event_type in ('Purchase','FormSubmit')) ndt, count(*) nde from de where customer_id is not null group by 1),
 t as (select customer_id, count(*) ntx, count(*) filter (where channel in ('App','Web')) ndig from tx group by 1)
 select corr(d.ndt, t.ndig) c_dig, corr(d.nde, t.ntx) c_all, count(*) n from d join t using(customer_id)""")
