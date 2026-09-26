"""hunt_08: chequeos de enlace a nivel producto: de.product_id pertenece al mismo cliente? tx por producto vs opened/last_tx."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
print('de.product_id owner match:', con.execute("""
SELECT count(*) n, count(p.product_id) in_pr, count(*) FILTER (WHERE p.customer_id = d.customer_id) same_cust,
 count(*) FILTER (WHERE d.customer_id IS NULL) de_cust_null
FROM (SELECT customer_id, product_id FROM de WHERE product_id IS NOT NULL) d LEFT JOIN pr p USING (product_id)""").fetchall())
print('tx before opened / after last_tx:', con.execute("""
SELECT count(*) n, count(*) FILTER (WHERE CAST(t.ts AS DATE) < p.opened) before_open,
 count(*) FILTER (WHERE t.ts > p.last_tx) after_lasttx, count(*) FILTER (WHERE p.expires < CAST(t.ts AS DATE)) after_exp
FROM tx t JOIN pr p USING (product_id)""").fetchall())
print('last_tx vs max tx ts:', con.execute("""
WITH m AS (SELECT product_id, max(ts) mx, count(*) n FROM tx GROUP BY 1)
SELECT count(*), count(*) FILTER (WHERE p.last_tx = m.mx) eq, avg(date_diff('day', m.mx, p.last_tx)) avg_diff,
 quantile_cont(date_diff('day', m.mx, p.last_tx), [0.05,0.5,0.95]) q, corr(epoch(p.last_tx), epoch(m.mx)) r
FROM pr p JOIN m USING (product_id) WHERE p.last_tx IS NOT NULL""").fetchall())
print('last_tx null by status:', con.execute("SELECT pstatus, count(*), count(last_tx) FROM pr GROUP BY 1").fetchall())
