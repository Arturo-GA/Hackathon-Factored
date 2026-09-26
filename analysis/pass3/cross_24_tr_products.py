# H18: producto mencionado en transcript (mentioned_entities.products) vs productos del cliente; plantilla de apertura vs productos
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("""create temp table t as select transcript_id, customer_id, json_extract_string(mentioned_entities,'$.products') prod,
  case when full_text like '%tarjeta de crédito%' then 'Tarjeta Crédito' when full_text like '%cuenta de ahorros%' then 'Cuenta Ahorro' else 'otro' end opening
  from tr""")
print(q("select prod, opening, count(*) from t group by 1,2 order by 3 desc"))
print(q("""select t.prod, count(*) n, avg((exists(select 1 from pr p where p.customer_id=t.customer_id and p.ptype=t.prod))::int) has_it,
  (select avg(h::int) from (select exists(select 1 from pr p where p.customer_id=c.customer_id and p.ptype=t.prod) h from (select customer_id from cu using sample 20000) c)) base
  from t where prod is not null group by 1"""))
print(q("""select t.opening, count(*) n, avg((exists(select 1 from pr p where p.customer_id=t.customer_id and p.ptype=t.opening))::int) has_it from t where opening<>'otro' group by 1"""))
