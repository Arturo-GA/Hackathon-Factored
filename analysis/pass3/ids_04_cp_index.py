# ids_04: ¿la FK rota cp.affected_product_id se puede reparar por índice de fila? (rn cliente reclamante vs rn producto / rn dueño)
import duckdb
con = duckdb.connect()
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=true")
q = lambda s: con.execute(s).fetchdf().to_string()
B='data/bronze'
con.execute(f"create temp table cu as select customer_id, file_row_number rn from read_parquet('{B}/customers.parquet', file_row_number=true)")
con.execute(f"create temp table pr as select product_id, customer_id, product_type, file_row_number rn from read_parquet('{B}/products.parquet', file_row_number=true)")
con.execute(f"""create temp table cp as select complaint_id, customer_id, affected_product_id, category, _source_file sf, file_row_number frn,
   file_row_number - min(file_row_number) over (partition by _source_file) rin from read_parquet('{B}/complaints.parquet', file_row_number=true)""")
con.execute("""create temp table j as select cp.*, c1.rn c_rn, p.rn p_rn, c2.rn o_rn, p.customer_id own_c from cp
   join cu c1 on c1.customer_id=cp.customer_id join pr p on p.product_id=cp.affected_product_id join cu c2 on c2.customer_id=p.customer_id""")
print(q("select count(*) n, corr(c_rn,p_rn) c_p, corr(c_rn,o_rn) c_o, corr(frn,p_rn) f_p, corr(frn, c_rn) f_c from j"))
for expr in ['p_rn - c_rn','o_rn - c_rn','p_rn - frn','o_rn - frn','p_rn - rin','(p_rn - c_rn + 400000) % 150000']:
    print(expr, q(f"select {expr} d, count(*) n from j group by 1 order by 2 desc limit 3"))
# ¿el producto afectado es el producto del cliente en la fila siguiente/anterior del reclamo?
con.execute("create temp table seq as select *, lag(customer_id) over (order by frn) prev_c, lead(customer_id) over (order by frn) next_c from cp")
print(q("""select avg((p.customer_id=prev_c)::int) prev, avg((p.customer_id=next_c)::int) nxt, count(*) from seq join pr p on p.product_id=seq.affected_product_id"""))
# ¿el dueño del producto afectado reclama alguna vez? ¿tiene más reclamos que un cliente al azar?
print(q("""select avg((own_c in (select customer_id from cp))::int) owner_complains from j"""))
print(q("""select count(distinct customer_id)*1.0/150000 frac_cust_complain from cp"""))
