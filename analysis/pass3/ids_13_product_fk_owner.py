# ids_13: ¿qué referencias a producto pertenecen al cliente de la fila? tx / de / cc.mentioned_products / cp.affected_product_id
# y ¿el producto referenciado es un sorteo uniforme de pr? (distribución de tipo y estado vs marginal)
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("""create temp table refs as
  select 'tx' src, customer_id, product_id from (select customer_id, product_id from tx using sample 200000)
  union all select 'de', customer_id, product_id from (select customer_id, product_id from de where product_id is not null and customer_id is not null using sample 200000)
  union all select 'cc_mentioned', customer_id, trim(unnest(string_split(mentioned_products, ','))) from cc where mentioned_products is not null
  union all select 'cp_affected', customer_id, affected_product_id from cp where affected_product_id is not null""")
print(q("""select src, count(*) n, avg((p.product_id is not null)::int) exists_in_pr, avg((p.customer_id=r.customer_id)::int) owned_by_row_customer,
   avg((exists(select 1 from pr p2 where p2.customer_id=r.customer_id))::int) row_cust_has_products,
   avg((p.pstatus='Active')::int) active, avg((p.ptype like 'Tarjeta%')::int) card from refs r left join pr p using(product_id) group by 1 order by 1"""))
print(q("select avg((pstatus='Active')::int) active, avg((ptype like 'Tarjeta%')::int) card from pr"))
