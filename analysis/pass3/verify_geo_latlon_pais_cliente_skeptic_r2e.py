import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('##',t), print(con.execute(s).df().to_string(), '\n'))
con.execute("""create temp table b as select t.customer_id, t.channel, t.ts, t.branch_id, cu.country cc,
  br.opened bopened, br.branch_status bstatus, br.branch_type btype
  from tx t join cu using(customer_id) join br on br.branch_id=t.branch_id""")
q("per-customer branch repetition vs random", """
with nbr as (select country, count(*) nbranch from br group by 1),
 c as (select customer_id, cc, count(*) ntx, count(distinct branch_id) d from b group by all having count(*) between 5 and 30)
select c.cc, count(*) ncust, round(avg(c.ntx),2) mean_ntx, round(avg(c.d),3) mean_distinct,
  round(avg(nbr.nbranch*(1-pow(1-1.0/nbr.nbranch, c.ntx))),3) expected_distinct_random
from c join nbr on nbr.country=c.cc group by 1 order by 1""")
q("tx before branch opened", """select count(*) n, sum((ts::date < bopened)::int) before_open, round(avg((ts::date < bopened)::int),4) rate_before_open from b""")
q("branch status x usage", "select bstatus, count(*) n, round(count(*)/sum(count(*)) over (),4) share_tx from b group by 1 order by 2 desc")
q("br status counts", "select branch_status, count(*) n, round(count(*)/sum(count(*)) over (),4) share_br from br group by 1")
q("channel x branch_type", "select channel, btype, count(*) n from b group by all order by 1,2")
