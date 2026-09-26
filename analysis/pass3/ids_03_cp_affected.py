# ids_03: complaints.affected_product_id (de otro cliente): ¿qué se conserva? tipo de producto vs categoría, país, moneda, orden de filas
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("""create temp table j as select cp.complaint_id, cp.customer_id cc_cust, cp.category, cp.subcategory, cp.currency cp_cur, cp.ts,
   p.product_id, p.customer_id p_cust, p.ptype, p.currency p_cur, p.pstatus, p.opened, c1.country c_country, c2.country p_country,
   c1.segment c_seg, c2.segment p_seg
   from cp join pr p on p.product_id=cp.affected_product_id join cu c1 on c1.customer_id=cp.customer_id join cu c2 on c2.customer_id=p.customer_id""")
print(q("select count(*) n, avg((cc_cust=p_cust)::int) same_cust, avg((c_country=p_country)::int) same_ctry, avg((cp_cur=p_cur)::int) same_cur, avg((c_seg=p_seg)::int) same_seg, avg((opened<=ts::date)::int) opened_before from j"))
# baseline: tasa esperada de mismo país si fuese al azar
print(q("select country, count(*)*1.0/sum(count(*)) over() shr from cu group by 1"))
print(q("select cp_cur, p_cur, count(*) n from j group by all order by n desc limit 12"))
print(q("select category, ptype, count(*) n from j group by all order by category, n desc"))
print(q("select ptype, count(*)*1.0/sum(count(*)) over() shr from pr group by 1"))
print(q("select pstatus, count(*)*1.0/sum(count(*)) over() shr from j group by 1"))
# el cliente reclamante tiene producto del tipo de la categoria?
print(q("""select avg((exists(select 1 from pr p where p.customer_id=j.cc_cust and p.ptype=j.ptype))::int) has_same_type,
   avg((exists(select 1 from pr p where p.customer_id=j.cc_cust))::int) has_any from j"""))
