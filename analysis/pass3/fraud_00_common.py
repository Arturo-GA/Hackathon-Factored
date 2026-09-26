import duckdb
def connect():
    con = duckdb.connect('data/analysis.duckdb', read_only=True)
    con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
    return con
def q(con, sql):
    return con.execute(sql).df()
