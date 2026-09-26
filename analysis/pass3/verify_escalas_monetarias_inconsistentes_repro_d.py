import duckdb, numpy as np, pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(s, title=None):
    if title: print('==', title)
    print(con.execute(s).df().to_string(), '\n')
q("""select event_type, count(*) n, count(customer_id) n_cust, min(event_value) mn, median(event_value) med, max(event_value) mx
     from de where event_value is not null group by 1 order by 2 desc""", "event_value por tipo")
q("""select count(*) n_all, count(event_value) n_val from de""")
# event_value vs pais del cliente (escala?)
q("""select cu.country, count(*) n, median(d.event_value) med, max(d.event_value) mx from de d join cu using(customer_id)
     where d.event_value is not null group by 1""", "event_value por pais cliente")
# match con tx mismo cliente ±1 dia, ±1% (original y USD-K)
con.execute("create temp table e as select event_id, customer_id, event_value v, ts from de where event_value is not null and customer_id is not null")
q("select count(*) n from e")
con.execute("""create temp table t as select customer_id, ts, amount,
   amount/(case currency when 'ARS' then 350.0 when 'COP' then 4000.0 else 1.0 end) usd from tx where customer_id in (select customer_id from e)""")
q("""select count(distinct e.event_id) n_orig from e join t on t.customer_id=e.customer_id and abs(epoch(t.ts)-epoch(e.ts))<86400 and abs(t.amount/e.v-1)<0.01""", "match ±1d ±1% original")
q("""select count(distinct e.event_id) n_usd from e join t on t.customer_id=e.customer_id and abs(epoch(t.ts)-epoch(e.ts))<86400 and abs(t.usd/e.v-1)<0.01""", "match ±1d ±1% USD")
q("""select count(distinct e.event_id) n_exact_anytime from e join t on t.customer_id=e.customer_id and round(t.amount,2)=round(e.v,2)""", "match exacto cualquier fecha")
# correlacion actividad digital vs n tx por cliente
q("""with d as (select customer_id, count(*) nde from de where customer_id is not null group by 1),
      x as (select customer_id, count(*) ntx from tx group by 1)
 select count(*) n, corr(d.nde, x.ntx) r_pearson, corr(rank_d, rank_x) r_spearman from (
   select d.nde, x.ntx, rank() over (order by d.nde) rank_d, rank() over (order by x.ntx) rank_x from d join x using(customer_id)) z
 cross join (select 1) dd, (select nde, ntx from d join x using(customer_id) limit 0) d2
""") if False else None
q("""with d as (select customer_id, count(*) nde from de where customer_id is not null group by 1),
      x as (select customer_id, count(*) ntx from tx group by 1),
      j as (select d.nde, x.ntx from d join x using(customer_id)),
      r as (select nde, ntx, rank() over (order by nde) rd, rank() over (order by ntx) rx from j)
 select count(*) n, corr(nde, ntx) r_pearson, corr(rd, rx) r_spearman from r""", "actividad digital vs n tx")
