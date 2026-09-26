import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
for t in ['tx','fx','pr','br','cu']:
    print(t, con.execute(f"DESCRIBE {t}").fetchall())
print(con.execute("select * from tx limit 3").df().T)
print(con.execute("select * from fx limit 15").df())
