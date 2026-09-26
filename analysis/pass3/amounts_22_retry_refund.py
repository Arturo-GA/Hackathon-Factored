import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
# duplicates of amount per customer
q("""with d as (select customer_id, amount, count(*) c from tx group by 1,2) select sum(c-1) dup_rows, count(*) filter (where c>1) dup_pairs, max(c) mx from d""")
# retry after decline: same customer same product, any tx within 24h with amount within 1%
con.execute("create temp table dcl as select transaction_id, customer_id, product_id, ts, amount, status, ttype from tx where status in ('Declined','Reversed','Pending')")
q("""select d.status, count(distinct d.transaction_id) n_follow_same_amt_1pct_7d from dcl d join tx t on t.product_id=d.product_id and t.transaction_id<>d.transaction_id
 and t.ts between d.ts and d.ts + interval 7 day and abs(t.amount/d.amount-1)<0.01 group by 1""")
q("select status, count(*) from dcl group by 1")
# baseline: approved tx sample
q("""with a as (select transaction_id, product_id, ts, amount from tx where status='Approved' using sample 90000 rows)
 select count(distinct a.transaction_id) n_follow, (select count(*) from a) n from a join tx t on t.product_id=a.product_id and t.transaction_id<>a.transaction_id
 and t.ts between a.ts and a.ts + interval 7 day and abs(t.amount/a.amount-1)<0.01""")
# next tx after decline: time gap and same ttype vs baseline
q("""with s as (select product_id, ts, status, ttype, lead(ts) over (partition by product_id order by ts) nts, lead(ttype) over (partition by product_id order by ts) nttype,
  lead(amount) over (partition by product_id order by ts) namt, amount from tx)
 select status, count(*) n, median(epoch(nts)-epoch(ts))/86400 med_gap_days, avg((nttype=ttype)::int) same_type, avg((abs(namt/amount-1)<0.05)::int) amt_within5 from s where nts is not null group by 1""")
