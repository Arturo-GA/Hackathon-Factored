"""hunt_00: esquema y cardinalidades de columnas categoricas (tx, cu, pr, cc, cp, sv)."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
for t in ['tx','cu','pr','cc','cp','sv','de','cs','ag','br','mc']:
    cols = con.execute(f"DESCRIBE {t}").fetchall()
    print(t, [(c[0], c[1]) for c in cols])
