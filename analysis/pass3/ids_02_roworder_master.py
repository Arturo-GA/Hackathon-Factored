# ids_02: orden de filas en tablas maestras: productos agrupados por cliente? orden de clientes = orden en customers?
import duckdb
con = duckdb.connect()
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=true")
q = lambda s: con.execute(s).fetchdf().to_string()
B='data/bronze'
con.execute(f"create temp table cu as select customer_id, registration_date, country, file_row_number rn from read_parquet('{B}/customers.parquet', file_row_number=true)")
con.execute(f"create temp table pr as select product_id, customer_id, product_type, opening_date, file_row_number rn from read_parquet('{B}/products.parquet', file_row_number=true)")
print(q("select * from pr order by rn limit 8"))
# productos consecutivos del mismo cliente?
print(q("""select avg((customer_id = lag_c)::int) same_as_prev from (select customer_id, lag(customer_id) over (order by rn) lag_c from pr)"""))
# correlacion entre rn producto y rn cliente
print(q("""select corr(p.rn, c.rn) corr_rn, count(*) from pr p join cu c using(customer_id)"""))
# productos ordenados por fecha de apertura?
print(q("""select corr(p.rn, epoch(try_cast(p.opening_date as date))) corr_open from pr p"""))
print(q("""select corr(rn, epoch(try_cast(registration_date as timestamp))) corr_reg from cu"""))
# customers orden por customer_id?
print(q("""select avg((customer_id > lag_c)::int) sorted_frac from (select customer_id, lag(customer_id) over (order by rn) lag_c from cu)"""))
# cuantos productos por cliente vs rn
print(q("""select c.rn//15000 dec, count(p.product_id)*1.0/count(distinct c.customer_id) prod_per_cust from cu c left join pr p using(customer_id) group by 1 order by 1"""))
