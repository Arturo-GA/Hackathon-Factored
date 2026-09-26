"""H4 duplicados por comercio/timestamp; consistencia merchant/mcat/tcat; Pending envejecidas; tx fuera de vigencia; amount_usd."""
import duckdb, pandas as pd, warnings
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width',250)
print("== mismo cliente + mismo comercio, siguiente compra ==")
print(q("""with w as (select customer_id, merchant_name, ts, amount, status,
   lead(ts) over (partition by customer_id, merchant_name order by ts) nts,
   lead(amount) over (partition by customer_id, merchant_name order by ts) namt from tx where merchant_name is not null)
 select count(*) n, sum(case when date_diff('minute',ts,nts)<=10 then 1 else 0 end) le10m,
   sum(case when date_diff('minute',ts,nts)<=60 then 1 else 0 end) le1h,
   sum(case when date_diff('hour',ts,nts)<=24 then 1 else 0 end) le24h,
   sum(case when date_diff('hour',ts,nts)<=24 and abs(namt-amount)<=0.01*amount then 1 else 0 end) le24h_mismo_monto
 from w""").to_string())
print("== colisiones de timestamp ==")
print(q("""select count(*) grupos, sum(c) filas from (select customer_id, ts, count(*) c from tx group by 1,2 having count(*)>1)""").to_string())
print(q("""select count(*) grupos, sum(c) filas from (select product_id, ts, count(*) c from tx group by 1,2 having count(*)>1)""").to_string())
print("== merchant -> mcat / tcat ==")
print(q("""select merchant_name, count(*) n, count(distinct mcat) n_mcat, mode(mcat) mcat_moda, avg(case when mcat=tcat then 1 else 0 end) mcat_eq_tcat,
  count(distinct country) n_pais, count(distinct currency) n_cur from tx where merchant_name is not null group by 1 order by 2 desc""").to_string())
print(q("""select avg(case when mcat=tcat then 1 else 0 end) eq, count(*) from tx where ttype='Purchase' and mcat is not null and tcat is not null""").to_string())
print("== Pending por antiguedad ==")
print(q("""select year(ts) y, count(*) n, avg(case when status='Pending' then 1 else 0 end) pend, avg(case when status='Reversed' then 1 else 0 end) rev from tx group by 1 order by 1""").to_string())
print(q("""select avg(case when ts < timestamp '2026-06-17' - interval 30 day then 1 else 0 end) pend_mas_30d, count(*) from tx where status='Pending'""").to_string())
print("== vigencia del producto vs tx ==")
print(q("""select t.status, count(*) n,
 avg(case when t.ts < p.opened then 1 else 0 end) antes_apertura,
 avg(case when t.ts > p.expires then 1 else 0 end) despues_venc,
 avg(case when t.ts < u.registration_date then 1 else 0 end) antes_registro,
 avg(case when p.last_tx is not null and t.ts > p.last_tx then 1 else 0 end) despues_last_tx
 from tx t join pr p using(product_id) join cu u on u.customer_id=t.customer_id group by 1""").round(4).to_string())
print(q("""with m as (select product_id, max(ts) mx, min(ts) mn from tx group by 1)
 select count(*) n, avg(case when p.last_tx is null then 1 else 0 end) lt_null,
  avg(case when cast(p.last_tx as date)=cast(m.mx as date) then 1 else 0 end) lt_eq_max,
  median(date_diff('day', m.mx, p.last_tx)) med_diff
 from m join pr p using(product_id)""").to_string())
print("== amount_usd ==")
print(q("""select currency, count(*) n, avg(case when amount_usd is null then 1 else 0 end) null_usd,
 min(amount/amount_usd) r_min, median(amount/amount_usd) r_med, max(amount/amount_usd) r_max from tx group by 1""").to_string())
print(q("""select src, dst, min(rate) mn, median(rate) med, max(rate) mx from fx where src='USD' group by 1,2""").to_string())
