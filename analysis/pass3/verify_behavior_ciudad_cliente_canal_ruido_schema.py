import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
for t in ['tx','cu','br']:
    print(t, con.execute(f"select column_name, data_type from information_schema.columns where table_name='{t}'").fetchall())
print(con.execute("select country, count(*) from cu group by 1 order by 2 desc").fetchall())
print(con.execute("select country, count(*) from br group by 1 order by 2 desc").fetchall())
print(con.execute("select country, count(*) from tx group by 1 order by 2 desc").fetchall())
print(con.execute("select country_raw, country, count(*) from tx group by 1,2 order by 3 desc limit 40").fetchall())
