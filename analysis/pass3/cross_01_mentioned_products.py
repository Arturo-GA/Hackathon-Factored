# H1: cc.mentioned_products -> pertenecen al cliente? tipo de producto vs motivo
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
print(q("select mentioned_products from cc where mentioned_products is not null limit 5"))
print(q("""select count(*) n, count(mentioned_products) nn,
 avg(len(string_split(mentioned_products, ','))) filter (where mentioned_products is not null) avg_k
 from cc"""))
con.execute("""create temp table mp as
 select interaction_id, customer_id, ts, cat, contact_reason, trim(u) pid
 from (select *, unnest(string_split(mentioned_products, ',')) u from cc where mentioned_products is not null)""")
print(q("""select count(*) n,
  avg((p.product_id is not null)::int) exists_rate,
  avg((p.customer_id = mp.customer_id)::int) own_rate
 from mp left join pr p on p.product_id = mp.pid"""))
# ownership by cat
print(q("""select cat, count(*) n, avg((p.customer_id = mp.customer_id)::int) own_rate
 from mp left join pr p on p.product_id=mp.pid group by 1 order by 1"""))
# do mentioned products belong to customer having products at all? fraction of customers' products mentioned
print(q("""select p.pstatus, count(*) n, avg((p.customer_id = mp.customer_id)::int) own
 from mp join pr p on p.product_id=mp.pid group by 1"""))
# ptype vs cat of mentioned products
print(q("""select mp.cat, p.ptype, count(*) n from mp join pr p on p.product_id=mp.pid group by 1,2 order by 1,3 desc"""))
