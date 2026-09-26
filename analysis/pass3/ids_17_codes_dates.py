# ids_17: ¿los códigos numéricos codifican fechas/secuencias? document_number vs dob (por tipo/país), product_number vs apertura,
# employee_code vs hire_date, branch_code vs apertura; email derivado del nombre
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("""select country, document_type, regexp_replace(regexp_replace(document_number,'[A-Z]','A','g'),'[0-9]','9','g') pat, count(*) n,
   corr(try_cast(regexp_replace(document_number,'[^0-9]','','g') as double), epoch(dob)) corr_dob,
   corr(try_cast(regexp_replace(document_number,'[^0-9]','','g') as double), epoch(registration_date)) corr_reg
   from cu group by all order by country, n desc"""))
print(q("""select ptype, corr(try_cast(regexp_replace(product_number,'[^0-9]','','g') as double), epoch(opened)) corr_open from pr group by 1"""))
print(q("""select corr(try_cast(substr(employee_code,2) as double), epoch(hire_date)) emp_hire from ag"""))
print(q("""select corr(try_cast(substr(branch_code,2) as double), epoch(opened)) br_open from br"""))
print(q("""select count(*) n,
   avg((strpos(lower(split_part(email,'@',1)), lower(strip_accents(split_part(last_name,' ',1))))>0)::int) email_has_last,
   avg((strpos(lower(split_part(email,'@',1)), lower(strip_accents(split_part(first_name,' ',1))))>0)::int) email_has_first
   from cu where email is not null"""))
print(q("""select regexp_replace(regexp_replace(split_part(email,'@',1),'[a-z]+','w','g'),'[0-9]+','9','g') pat, count(*) n from cu where email is not null group by 1 order by 2 desc limit 8"""))
