# H17: pr.app vs tx canal App; de.ip_country extranjero vs tx extranjera/fraude; de.platform vs canal tx
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("""select p.app, count(*) n, round(avg((t.channel='App')::int),4) p_app, round(avg((t.channel='Web')::int),4) p_web from tx t join pr p using(product_id) group by 1"""))
print(q("""select p.opening_channel, count(*) n, round(avg((t.channel='App')::int),4) p_app, round(avg((t.channel='Branch')::int),4) p_branch, round(avg((t.channel='Web')::int),4) p_web from (select * from tx using sample 300000) t join pr p using(product_id) group by 1"""))
print(q("select ip_country, count(*) from de group by 1 order by 2 desc limit 10"))
# ip_country vs pais cliente
print(q("""select c.country, d.ip_country, count(*) n from (select customer_id, ip_country from de where customer_id is not null using sample 300000) d join cu c using(customer_id) group by 1,2 order by 1,3 desc"""))
# foreign tx share by customer vs foreign ip share
print(q("""with t as (select customer_id, avg((country<>(select country from cu where cu.customer_id=tx.customer_id))::int) ftx from tx where hash(customer_id)%20=0 group by 1),
 d as (select d.customer_id, avg((d.ip_country<>replace(c.country,'México','Mexico'))::int) fip from de d join cu c using(customer_id) where hash(d.customer_id)%20=0 group by 1)
 select count(*) n, corr(ftx, fip) r from t join d using(customer_id)"""))
