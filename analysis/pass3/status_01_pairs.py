"""H1-H4: emparejamiento Reversed/Pending/Declined con transacciones gemelas y duplicados."""
import duckdb, time
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
t0=time.time()
# base: cuantas tx por producto, granularidad de ts
print(q("""select count(distinct product_id) np, count(distinct customer_id) nc,
  avg(case when second(ts)=0 then 1 else 0 end) sec0,
  count(*)/count(distinct product_id) tx_per_prod from tx""").to_string())
# H1: Reversed -> gemela (mismo producto, mismo monto) en cualquier otro momento
for st in ['Reversed','Pending','Declined','Approved']:
    r = q(f"""
    with s as (select transaction_id, product_id, amount, ts from tx where status='{st}' using sample 20000 rows),
    j as (select s.transaction_id, t.status st2, t.ts - s.ts dt
          from s join tx t on t.product_id=s.product_id and t.amount=s.amount and t.transaction_id<>s.transaction_id)
    select '{st}' base, count(distinct transaction_id) con_gemela, (select count(*) from s) n,
      count(*) pares, 
      sum(case when st2='Approved' then 1 else 0 end) gem_approved
    from j""")
    print(r.to_string(), f"{time.time()-t0:.0f}s")
# mismo cliente mismo monto (cualquier producto)
r = q("""with s as (select transaction_id, customer_id, amount, ts, status from tx where status<>'Approved' using sample 30000 rows)
select s.status, count(distinct s.transaction_id) con_gemela_cliente
from s join tx t on t.customer_id=s.customer_id and t.amount=s.amount and t.transaction_id<>s.transaction_id group by 1""")
print(r.to_string())
# unicidad de montos: cuantos montos repetidos globalmente
print(q("""select avg(case when c>1 then 1 else 0 end) frac_montos_repetidos_en_producto from
 (select product_id, amount, count(*) c from tx group by 1,2)""").to_string())
