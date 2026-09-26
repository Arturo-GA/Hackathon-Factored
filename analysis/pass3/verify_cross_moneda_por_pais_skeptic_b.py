# Verificador escéptico (b): claimed vs montos de tx del propio cliente vs placebo; medianas de tx por moneda
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("select currency, round(median(amount),1) med, round(quantile_cont(amount,0.1),1) p10, round(quantile_cont(amount,0.9),1) p90 from tx group by 1"))
con.execute("create temp table c2 as select complaint_id, customer_id, claimed, currency, subcategory, lead(customer_id) over (order by hash(complaint_id)) other from cp where claimed is not null")
con.execute("create temp table txc as select customer_id, amount, amount_usd, currency tcur from tx where customer_id in (select customer_id from c2 union select other from c2)")
print(q("select count(*) nc, (select count(*) from txc) ntx from c2"))
print(q("""select coalesce(c2.currency,'NULL') cur, count(*) n,
  round(avg((exists(select 1 from txc t where t.customer_id=c2.customer_id and abs(t.amount-c2.claimed)<=0.005*c2.claimed))::int),4) own,
  round(avg((exists(select 1 from txc t where t.customer_id=c2.other and abs(t.amount-c2.claimed)<=0.005*c2.claimed))::int),4) placebo,
  round(avg((exists(select 1 from txc t where t.customer_id=c2.customer_id and abs(coalesce(t.amount_usd,t.amount)-c2.claimed)<=0.005*c2.claimed))::int),4) own_usd,
  round(avg((exists(select 1 from txc t where t.customer_id=c2.other and abs(coalesce(t.amount_usd,t.amount)-c2.claimed)<=0.005*c2.claimed))::int),4) plac_usd
  from c2 group by rollup(1) order by 1"""))
print(q("select subcategory, count(*) n from cp where claimed is not null group by 1 order by 2 desc limit 8"))
