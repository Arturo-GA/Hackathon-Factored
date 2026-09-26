import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
for t in ['tx','cu','pr']:
    print(t, con.execute(f"select column_name, data_type from information_schema.columns where table_name='{t}'").fetchall())
print(con.execute("select table_name, table_type from information_schema.tables").fetchall())
print(con.execute("select count(*), min(amount), max(amount), sum((amount is null)::int) from tx").fetchall())
print(con.execute("select ttype, currency, count(*) n from tx group by all order by 1,2").fetchall())
