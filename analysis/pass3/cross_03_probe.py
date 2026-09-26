import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("select cat, contact_reason, count(*) n from cc group by 1,2 order by 1,3 desc"))
print(q("select event_type, event_category, action, count(*) n, count(event_value) nv, count(product_id) np, avg(event_value) av from de group by 1,2,3 order by 4 desc limit 60"))
