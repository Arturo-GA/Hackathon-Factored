import duckdb, numpy as np, pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(s, title=None):
    if title: print('==', title)
    print(con.execute(s).df().to_string(), '\n')
con.execute("create temp table c as select complaint_id, customer_id, claimed, currency, ts from cp where claimed is not null")
con.execute("""create temp table t as select customer_id, amount, currency, ts,
   amount/(case currency when 'ARS' then 350.0 when 'COP' then 4000.0 else 1.0 end) usd_k,
   coalesce(amount_usd, case when currency='USD' then amount end) usd_col
   from tx where customer_id in (select customer_id from c)""")
q("select count(*) n_tx_of_claimants, (select count(*) from c) n_claims, (select count(distinct customer_id) from c) n_cust from t")
# exact (2 dec) same customer, original amount
q("""select count(distinct c.complaint_id) n from c join t on t.customer_id=c.customer_id and round(t.amount,2)=round(c.claimed,2)""", "match exacto misma persona, monto original")
q("""select count(distinct c.complaint_id) n from c join t on t.customer_id=c.customer_id and abs(t.usd_k-c.claimed)<0.01""", "match misma persona, USD (K fijo)")
q("""select count(distinct c.complaint_id) n from c join t on t.customer_id=c.customer_id and abs(t.usd_col-c.claimed)<0.01""", "match misma persona, amount_usd")
# tolerancia relativa 1%, mismo cliente, tx anterior al reclamo en 90d
q("""select count(distinct c.complaint_id) n from c join t on t.customer_id=c.customer_id and abs(t.amount/c.claimed-1)<0.01
     and t.ts between c.ts - interval 90 day and c.ts""", "match ±1% misma persona 90d previos, original")
q("""select count(distinct c.complaint_id) n from c join t on t.customer_id=c.customer_id and abs(t.usd_k/c.claimed-1)<0.01
     and t.ts between c.ts - interval 90 day and c.ts""", "match ±1% misma persona 90d previos, USD")
# azar: tasa de match ±1% esperada. Comparar contra cliente permutado
con.execute("""create temp table c2 as select complaint_id, claimed, ts,
  (select customer_id from c cc order by random() limit 1) dummy from c limit 1""")
# baseline: shuffle customers among claims
con.execute("""create temp table cperm as with a as (select complaint_id, claimed, ts, row_number() over (order by random()) r from c),
   b as (select customer_id, row_number() over (order by random()) r from c)
   select a.complaint_id, a.claimed, a.ts, b.customer_id from a join b using(r)""")
q("""select count(distinct c.complaint_id) n from cperm c join t on t.customer_id=c.customer_id and abs(t.amount/c.claimed-1)<0.01
     and t.ts between c.ts - interval 90 day and c.ts""", "baseline permutado ±1% 90d original")
# any customer exact USD match
q("""select count(distinct c.complaint_id) n from c join (select distinct round(amount,2) a from tx where currency='USD') u on u.a=round(c.claimed,2)""", "match exacto con cualquier tx USD de cualquier cliente")
q("select count(distinct round(amount,2)) nd, count(*) n from tx where currency='USD' and amount between 50 and 5000")
