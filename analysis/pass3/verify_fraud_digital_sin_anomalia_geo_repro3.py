"""Verificación (3): tasa ±24h de eventos del cliente alrededor de tx App/Web en la muestra hash%50 del script original vs población completa."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
con.execute("""CREATE TEMP TABLE si AS SELECT min(customer_id) customer_id, min(ts) t0, max(ts) t1
  FROM de WHERE customer_id IS NOT NULL GROUP BY session_id""")
print(con.execute("""
WITH t AS (SELECT transaction_id, customer_id, ts, fraud, (hash(transaction_id)%50=0) enmuestra FROM tx WHERE channel IN ('App','Web')),
h AS (SELECT DISTINCT t.transaction_id FROM t JOIN si ON si.customer_id=t.customer_id
      AND t.ts BETWEEN si.t0 - INTERVAL 1 DAY AND si.t1 + INTERVAL 1 DAY)
SELECT fraud, enmuestra, count(*) n, count(h.transaction_id) hit, round(100.0*count(h.transaction_id)/count(*),3) pct
FROM t LEFT JOIN h USING(transaction_id) GROUP BY ALL ORDER BY 1,2""").df().to_string(index=False))
