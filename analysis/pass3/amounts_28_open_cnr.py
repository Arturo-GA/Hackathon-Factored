import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
q("""select year(p.opened) y, count(*) n, avg((t.ts::date < p.opened)::int) before_open, median(datediff('day', t.ts::date, p.opened)) filter (where t.ts::date<p.opened) med_days_before
 from tx t join pr p using(product_id) group by 1 order by 1""")
q("""select (t.ts::date < p.opened) before_open, count(*) n, avg((t.status='Declined')::int) decl, avg(t.fraud::int)*1000 fraud_pm from tx t join pr p using(product_id) group by 1""")
# customers with 'Cargo no reconocido' complaints vs rest: tx amount / foreign / fraud / declines
q("""with c as (select distinct customer_id from cp where subcategory='Cargo no reconocido'),
 t as (select t.customer_id, avg(t.amount/(case t.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)) a, avg((t.country<>cu.country)::int) fr, sum(t.fraud::int) nf,
  avg((t.status='Declined')::int) d, count(*) n from tx t join cu using(customer_id) group by 1)
 select (c.customer_id is not null) cnr, count(*) ncust, avg(a) mean_amt, avg(fr) foreign_share, avg((nf>0)::int) any_fraud, avg(d) decl, avg(n) ntx from t left join c using(customer_id) group by 1""")
