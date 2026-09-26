"""Verificador: esquema de pr/cu/tx relevantes (tipos de columnas)."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
for t in ['pr', 'cu', 'tx']:
    print(t)
    print(con.execute(f"DESCRIBE {t}").df()[['column_name', 'column_type']].to_string())
print(con.execute("SELECT pstatus, count(*) n, count(last_tx) n_lt, min(opened), max(opened), min(expires), max(expires), min(last_tx), max(last_tx), min(last_updated), max(last_updated) FROM pr GROUP BY 1").df().to_string())
print(con.execute("SELECT ptype, count(*) n, count(expires) n_exp, count(credit_limit) n_cl FROM pr GROUP BY 1 ORDER BY 2 DESC").df().to_string())
