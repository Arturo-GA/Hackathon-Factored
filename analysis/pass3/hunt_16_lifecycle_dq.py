"""hunt_16: consistencia de ciclo de vida producto/cliente vs transacciones (calidad de datos a nivel producto):
 tx antes de apertura del producto, tx despues de vencimiento, tx antes del registro del cliente, pr.last_tx vs max(tx.ts), de.product_id de otro cliente."""
import duckdb
import pandas as pd
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
print(con.execute("""SELECT count(*) n,
  avg(CASE WHEN CAST(t.ts AS DATE) < p.opened THEN 1.0 ELSE 0 END) before_open,
  avg(CASE WHEN p.expires IS NOT NULL AND CAST(t.ts AS DATE) > p.expires THEN 1.0 ELSE 0 END) after_exp,
  avg(CASE WHEN t.ts < c.registration_date THEN 1.0 ELSE 0 END) before_reg,
  avg(CASE WHEN p.opened < CAST(c.registration_date AS DATE) THEN 1.0 ELSE 0 END) prod_before_reg,
  avg(CASE WHEN date_diff('year', c.dob, CAST(t.ts AS DATE)) < 18 THEN 1.0 ELSE 0 END) minor_at_tx,
  avg(CASE WHEN t.ts > p.last_tx THEN 1.0 ELSE 0 END) after_lasttx
  FROM tx t JOIN pr p USING (product_id) JOIN cu c ON c.customer_id = t.customer_id""").df().T.round(4).to_string())
print('por anio de apertura:')
print(con.execute("""SELECT year(p.opened) yr, count(*) n, avg(CASE WHEN CAST(t.ts AS DATE) < p.opened THEN 1.0 ELSE 0 END) before_open
  FROM tx t JOIN pr p USING (product_id) GROUP BY 1 ORDER BY 1""").df().T.round(3).to_string())
print('rango fechas pr.opened / cu.registration_date:', con.execute("SELECT min(opened), max(opened) FROM pr").fetchall(), con.execute("SELECT min(registration_date), max(registration_date) FROM cu").fetchall())
print('last_tx vs max(tx.ts) por producto:', con.execute("""WITH m AS (SELECT product_id, max(ts) mx FROM tx GROUP BY 1)
  SELECT count(*) n, count(p.last_tx) n_lasttx, avg(CASE WHEN p.last_tx = m.mx THEN 1.0 ELSE 0 END) exact,
   avg(CASE WHEN abs(date_diff('day', m.mx, p.last_tx)) <= 1 THEN 1.0 ELSE 0 END) within1d, corr(epoch(p.last_tx), epoch(m.mx)) r
  FROM pr p JOIN m USING (product_id)""").fetchall())
print('Active sin tx:', con.execute("SELECT count(*) FROM pr p WHERE pstatus='Active' AND NOT EXISTS (SELECT 1 FROM tx t WHERE t.product_id=p.product_id)").fetchall())
print('de.product_id -> dueno:', con.execute("""SELECT count(*) n, count(p.product_id) in_pr, count(*) FILTER (WHERE p.customer_id = d.customer_id) same_cust,
  count(*) FILTER (WHERE d.customer_id IS NULL) de_cust_null FROM (SELECT customer_id, product_id FROM de WHERE product_id IS NOT NULL) d LEFT JOIN pr p USING (product_id)""").fetchall())
print('cc.mentioned_products -> dueno:', con.execute("""WITH m AS (SELECT customer_id, trim(unnest(string_split(mentioned_products, ','))) pid FROM cc WHERE mentioned_products IS NOT NULL)
  SELECT count(*) n, count(p.product_id) in_pr, count(*) FILTER (WHERE p.customer_id = m.customer_id) same_cust FROM m LEFT JOIN pr p ON p.product_id = m.pid""").fetchall())
