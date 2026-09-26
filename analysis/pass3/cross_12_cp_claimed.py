# H8: cp.claimed vs montos de tx del cliente (cualquier producto; directo, USD y convertido con fx); cp.currency vs moneda del cliente
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
# moneda del cliente
con.execute("""create temp table cur as select c.customer_id, c.country,
   case c.country when 'México' then 'MXN' when 'Colombia' then 'COP' when 'Argentina' then 'ARS' end ccy_country,
   (select string_agg(distinct p.currency, ',') from pr p where p.customer_id=c.customer_id) prod_ccy
   from cu c where c.customer_id in (select customer_id from cp)""")
print(q("select country, prod_ccy, count(*) from cur group by 1,2 order by 3 desc limit 12"))
print(q("""select cp.currency, count(*) n, avg((cp.currency=cur.ccy_country)::int) eq_country,
   avg((position(cp.currency in coalesce(cur.prod_ccy,''))>0)::int) in_prod_ccy
   from cp join cur using(customer_id) where cp.currency is not null group by 1"""))
print(q("""select cur.country, cp.currency, count(*) n from cp join cur using(customer_id) group by 1,2 order by 1,2"""))
# claimed vs tx amounts: exact / within 0.5% in native, in amount_usd, and converted to cp.currency via fx
con.execute("""create temp table c2 as select complaint_id, customer_id, ts, claimed, currency, subcategory from cp where claimed is not null""")
con.execute("""create temp table txc as select customer_id, ts, amount, amount_usd, currency tcur from tx where customer_id in (select customer_id from c2)""")
print(q("select count(*) from c2"), q("select count(*) from txc"))
print(q("""select count(*) n,
   avg((exists(select 1 from txc t where t.customer_id=c2.customer_id and abs(t.amount-c2.claimed)<=0.005*c2.claimed))::int) near_amt,
   avg((exists(select 1 from txc t where t.customer_id=c2.customer_id and abs(t.amount_usd-c2.claimed)<=0.005*c2.claimed))::int) near_usd,
   avg((exists(select 1 from txc t where t.customer_id=c2.customer_id and round(t.amount,2)=round(c2.claimed,2)))::int) exact_amt,
   avg((exists(select 1 from txc t where t.customer_id=c2.customer_id and t.ts < c2.ts and t.ts > c2.ts - interval 90 day and abs(t.amount-c2.claimed)<=0.005*c2.claimed))::int) near_amt_90d
 from c2"""))
# placebo: shuffle customer (compare to other customer's tx) -> random pairing
print(q("""with p as (select c2.*, lead(customer_id) over (order by hash(complaint_id)) other from c2)
 select count(*) n, avg((exists(select 1 from txc t where t.customer_id=p.other and abs(t.amount-p.claimed)<=0.005*p.claimed))::int) near_amt_placebo
 from p where other is not null"""))
# converted: tx amount -> cp.currency using fx on tx date
print(q("select src,dst,count(*) from fx group by 1,2 order by 1,2"))
print(q("""select count(*) n, avg(hit::int) conv_hit from (
  select c2.complaint_id, bool_or(abs(t.amount*f.rate - c2.claimed) <= 0.005*c2.claimed) hit
  from c2 join txc t on t.customer_id=c2.customer_id
  join fx f on f.date=cast(t.ts as date) and f.src=t.tcur and f.dst=c2.currency
  where c2.currency is not null and c2.currency<>t.tcur group by 1)"""))
# claimed distribution by customer ccy -> is claimed scale consistent with tx scale?
print(q("""select cur.ccy_country, round(median(c2.claimed),1) med_claim,
   (select round(median(amount),1) from tx t join cu c using(customer_id) where c.country=cur.country) med_tx
   from c2 join cur using(customer_id) group by cur.ccy_country, cur.country"""))
