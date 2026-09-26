"""Escéptico (reintento r2), sección 0: esquema/valores básicos para diseñar las pruebas."""
import duckdb, pandas as pd
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
print(q("DESCRIBE tx")[['column_name','column_type']].T.to_string())
print(q("SELECT transaction_id, product_id, customer_id, ts, process_date, ttype, tcat, channel, mcat, amount, status FROM tx USING SAMPLE 5 ROWS").to_string())
print(q("SELECT ptype, count(*) n_prod, sum((pstatus='Active')::INT) n_active FROM pr GROUP BY 1 ORDER BY 1").to_string())
print(q("SELECT ttype, count(*) n FROM tx GROUP BY 1 ORDER BY 2 DESC").to_string())
