# H25: prefijo telefonico vs pais del cliente (verificacion de identidad)
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("""select country, split_part(mobile_phone,' ',1) pref, count(*) n, round(count(*)*1.0/sum(count(*)) over (partition by country),3) shr from cu group by 1,2 order by 1,3 desc"""))
print(q("""select country, split_part(landline_phone,' ',1) pref, count(*) n from cu group by 1,2 order by 1,3 desc"""))
