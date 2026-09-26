import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
q("select country_raw, country, count(*) n from tx group by all order by 2, n desc")
q("select country, city, count(*) n from tx group by all order by 1, n desc")
