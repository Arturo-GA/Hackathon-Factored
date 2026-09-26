import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
for t in ['tx','cc','cp','de','cs','pr','fx','mc','br','cu']:
    print(t, con.execute(f"select column_name||':'||data_type from information_schema.columns where table_name='{t}'").fetchall())
