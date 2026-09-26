"""Sondeo inicial: formato crudo de transaction_date/process_date, rangos y nulos."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
raw = duckdb.connect()
raw.execute("SET memory_limit='500MB'; SET threads=2")
print(raw.execute("SELECT transaction_date, process_date, transaction_country, currency FROM 'data/bronze/transactions.parquet' USING SAMPLE 12 ROWS").fetchdf().to_string())
print(raw.execute("SELECT length(transaction_date) l, count(*) n FROM 'data/bronze/transactions.parquet' GROUP BY 1 ORDER BY 2 DESC").fetchdf())
print(con.execute("""SELECT min(ts), max(ts), min(process_date), max(process_date), count(*) n,
  sum(ts IS NULL::INT) nts, sum((process_date IS NULL)::INT) npd FROM tx""").fetchdf().to_string())
print(con.execute("""SELECT date_diff('day', ts::DATE, process_date) d, count(*) n FROM tx GROUP BY 1 ORDER BY 1""").fetchdf().to_string())
