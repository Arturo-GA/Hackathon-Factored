import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
q("describe de")
q("select event_type, event_category, count(*) n, avg((event_value is not null)::int) val_nn, avg((product_id is not null)::int) prod_nn from de group by all order by n desc limit 30")
