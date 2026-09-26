"""H1-H4 completos: gemelas exactas, siguiente tx tras cada estado, cargos duplicados por comercio."""
import duckdb, time
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
t0=time.time()
# gemelas exactas (producto+monto) para todos los no-Approved
print(q("""with s as (select transaction_id, product_id, amount, status from tx where status<>'Approved')
select s.status, count(*) n_pares, count(distinct s.transaction_id) n_con_gemela
from s join tx t on t.product_id=s.product_id and t.amount=s.amount and t.transaction_id<>s.transaction_id group by 1""").to_string(), f"{time.time()-t0:.0f}s")
print(q("select status, count(*) from tx where status<>'Approved' group by 1").to_string())
# gemela aproximada: mismo cliente, monto dentro de 1%, dentro de 24h
print(q("""with s as (select transaction_id, customer_id, amount, ts, status from tx where status in ('Reversed','Pending','Declined'))
select s.status, count(distinct s.transaction_id) n_con_gemela_aprox
from s join tx t on t.customer_id=s.customer_id and t.transaction_id<>s.transaction_id
 and t.ts between s.ts - interval 1 day and s.ts + interval 1 day and abs(t.amount - s.amount) <= 0.01*s.amount
group by 1""").to_string(), f"{time.time()-t0:.0f}s")
# distribucion del gap a la siguiente tx del mismo cliente segun estado actual
print(q("""with w as (select customer_id, status, ts, amount, merchant_name,
   lead(ts) over (partition by customer_id order by ts) nts,
   lead(status) over (partition by customer_id order by ts) nst,
   lead(amount) over (partition by customer_id order by ts) namt
 from tx)
select status, count(*) n,
  avg(case when date_diff('minute', ts, nts) <= 10 then 1 else 0 end) next_10min,
  avg(case when date_diff('minute', ts, nts) <= 60 then 1 else 0 end) next_1h,
  median(date_diff('hour', ts, nts)) med_gap_h,
  avg(case when nst='Approved' then 1 else 0 end) next_approved,
  avg(case when nst='Declined' then 1 else 0 end) next_declined,
  avg(case when abs(namt-amount)<=0.05*amount then 1 else 0 end) next_amt_5pct
from w group by 1 order by 1""").to_string(), f"{time.time()-t0:.0f}s")
