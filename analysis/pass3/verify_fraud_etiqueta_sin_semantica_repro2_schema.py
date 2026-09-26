"""Sondeo de esquema para la verificación de fraud_etiqueta_sin_semantica (tipos de columnas y valores distintos)."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
for r in con.execute("DESCRIBE tx").fetchall():
    print(r[0], r[1])
print(con.execute("SELECT ttype, tcat, count(*) n, sum(fraud::int) f, min(amount) mn, max(amount) mx, sum((amount<0)::int) nneg FROM tx GROUP BY 1,2 ORDER BY 1,2").df().to_string(index=False))
print(con.execute("SELECT status, code, count(*) n FROM tx GROUP BY 1,2 ORDER BY 1,2").df().to_string(index=False))
print(con.execute("SELECT count(*) n, count(fraud) nn_fraud, sum(fraud::int) f, count(fscore) nn_fs FROM tx").df().to_string(index=False))
