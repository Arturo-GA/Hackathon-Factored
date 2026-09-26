import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
print(con.execute("DESCRIBE tx").fetchdf().to_string())
print(con.execute("select status, code, count(*) n from tx group by 1,2 order by 1,2").fetchdf().to_string())
print(con.execute("select ttype, status, count(*) n from tx group by 1,2 order by 1,2").fetchdf().to_string())
print(con.execute("select * from tx using sample 5 rows").fetchdf().T.to_string())
