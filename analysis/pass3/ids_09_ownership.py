# ids_09: consistencia de propiedad: tx.customer_id = dueño de tx.product_id; de.product_id del mismo cliente; duplicados product_number / employee_code
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("select count(*) n, avg((t.customer_id=p.customer_id)::int) same_owner from (select customer_id, product_id from tx using sample 300000) t join pr p using(product_id)"))
print(q("select count(*) n, avg((d.customer_id=p.customer_id)::int) same_owner from (select customer_id, product_id from de where product_id is not null and customer_id is not null using sample 300000) d join pr p using(product_id)"))
print(q("""select p.product_number, p.ptype, p.customer_id, p.product_id, p.pstatus, p.opened from pr p where product_number in (select product_number from pr group by 1 having count(*)>1) order by 1"""))
print(q("""select a.employee_code, a.agent_id, a.first_name, a.last_name, a.country_of_origin, a.agent_status, a.hire_date from ag a where employee_code in (select employee_code from ag group by 1 having count(*)>1) order by 1 limit 12"""))
print(q("""select count(*) n_dup_codes from (select employee_code from ag group by 1 having count(*)>1)"""))
