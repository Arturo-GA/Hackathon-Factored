# H2: universo de product_id: cc.mentioned_products, tx, de, cp -> existen en pr? de quien?
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
con.execute("""create temp table mp as
 select interaction_id, customer_id, ts, cat, contact_reason, trim(u) pid
 from (select *, unnest(string_split(mentioned_products, ',')) u from cc where mentioned_products is not null)""")
print("mentioned distinct:", q("select count(*) n, count(distinct pid) nd from mp"))
print("tx product in pr / owner:", q("""select count(*) n, avg((p.product_id is not null)::int) ex, avg((p.customer_id=t.customer_id)::int) own
  from (select product_id, customer_id from tx using sample 300000) t left join pr p using(product_id)"""))
print("de product:", q("""select count(*) n, count(product_id) nn from de"""))
print("de product in pr / owner:", q("""select count(*) n, avg((p.product_id is not null)::int) ex, avg((p.customer_id=d.customer_id)::int) own,
  avg((d.customer_id is null)::int) nocust
  from (select product_id, customer_id from de where product_id is not null using sample 300000) d left join pr p using(product_id)"""))
print("cp affected in pr:", q("""select count(*) n, count(affected_product_id) nn, avg((p.product_id is not null)::int) ex from cp left join pr p on p.product_id=cp.affected_product_id"""))
# mentioned ids present in tx.product_id / de.product_id / cp?
print("mentioned in tx products:", q("""select avg((pid in (select distinct product_id from tx))::int) r from (select distinct pid from mp)"""))
print("mentioned in de products:", q("""select avg((pid in (select distinct product_id from de where product_id is not null))::int) r from (select distinct pid from mp)"""))
print("mentioned in cp affected:", q("""select avg((pid in (select distinct affected_product_id from cp where affected_product_id is not null))::int) r from (select distinct pid from mp)"""))
# id format
print(q("select length(pid) l, count(*) from mp group by 1"))
print(q("select length(product_id) l, count(*) from pr group by 1"))
