"""H12: coherencia temporal tx vs ciclo de vida: productos (opened, expires, last_tx, last_updated) y clientes (registration_date).
¿Hay tx antes de abrir el producto / registrar al cliente? ¿pr.last_tx = max(tx.ts) del producto?"""
import duckdb, pandas as pd
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
print(con.execute("SELECT min(opened), max(opened), min(expires), max(expires), min(last_tx), max(last_tx), min(last_updated), max(last_updated), avg((last_tx IS NULL)::INT) lt_null FROM pr").fetchdf().T)
print(con.execute("SELECT min(registration_date), max(registration_date), min(last_updated), max(last_updated) FROM cu").fetchdf().T)
agg = """CREATE TEMP TABLE pagg AS SELECT product_id, count(*) n, min(ts) first_ts, max(ts) last_ts, min(process_date) first_pd, max(process_date) last_pd FROM tx GROUP BY 1"""
con.execute(agg)
print(con.execute("""SELECT count(*) n_prod_with_tx,
  avg((a.first_ts < p.opened)::INT) share_tx_before_open,
  avg((a.last_ts > p.expires)::INT) share_tx_after_expiry,
  avg((p.last_tx IS NOT NULL)::INT) has_last_tx,
  avg((p.last_tx = a.last_ts)::INT) lasttx_eq_maxts,
  avg((p.last_tx::DATE = a.last_pd)::INT) lasttx_date_eq_maxpd,
  avg((p.last_tx < a.last_ts)::INT) lasttx_before_maxts,
  avg((p.last_tx > a.last_ts)::INT) lasttx_after_maxts,
  median(date_diff('day', a.last_ts, p.last_tx)) med_gap_days
  FROM pagg a JOIN pr p USING(product_id)""").fetchdf().T)
print(con.execute("""SELECT p.pstatus, count(*) n, avg((a.product_id IS NOT NULL)::INT) has_tx, avg((p.last_tx IS NOT NULL)::INT) has_lasttx,
  avg((a.first_ts < p.opened)::INT) before_open
  FROM pr p LEFT JOIN pagg a USING(product_id) GROUP BY 1""").fetchdf().to_string(index=False))
# distribución del gap last_tx vs max ts (días)
print(con.execute("""SELECT quantile_cont(date_diff('day', a.last_ts, p.last_tx), [0.01,0.1,0.25,0.5,0.75,0.9,0.99]) q FROM pagg a JOIN pr p USING(product_id) WHERE p.last_tx IS NOT NULL""").fetchdf().q[0])
# fracción de tx de un producto que caen antes de opened
print(con.execute("""SELECT count(*) n, avg((t.ts < p.opened)::INT) tx_before_open, avg((t.ts > p.expires)::INT) tx_after_exp FROM tx t JOIN pr p USING(product_id)""").fetchdf())
# opened distribución vs ventana tx
print(con.execute("""SELECT year(opened) y, count(*) n FROM pr GROUP BY 1 ORDER BY 1""").fetchdf().T)
# tx vs registro del cliente
print(con.execute("""WITH c AS (SELECT customer_id, min(ts) f, max(ts) l, count(*) n FROM tx GROUP BY 1)
  SELECT count(*) n, avg((c.f < cu.registration_date)::INT) tx_before_reg, median(date_diff('day', cu.registration_date, c.f)) med_days_reg_to_first,
  avg((c.l > cu.last_updated)::INT) tx_after_lastupd FROM c JOIN cu USING(customer_id)""").fetchdf().T)
# tx dentro del periodo: ¿los productos abiertos durante 2023-2026 empiezan a transaccionar tras abrir?
print(con.execute("""SELECT (p.opened >= TIMESTAMP '2023-06-17') opened_in_window, count(*) n_prod, avg(a.n) avg_tx,
  avg((a.first_ts >= p.opened)::INT) first_after_open,
  median(date_diff('day', p.opened, a.first_ts)) med_open_to_first
  FROM pr p JOIN pagg a USING(product_id) GROUP BY 1""").fetchdf().to_string(index=False))
# resumen: tx fuera de la vida del producto (antes de abrir o después de vencer)
print(con.execute("""SELECT count(*) n, avg((t.ts < p.opened OR t.ts > p.expires)::INT) tx_outside_life,
  avg(((t.ts < p.opened OR t.ts > p.expires) AND t.status='Approved')::INT) share_approved_outside FROM tx t JOIN pr p USING(product_id)""").fetchdf().T)
print(con.execute("""SELECT (t.ts < p.opened OR t.ts > p.expires) outside, count(*) n, avg((t.status='Declined')::INT) decl FROM tx t JOIN pr p USING(product_id) GROUP BY 1""").fetchdf().to_string(index=False))
# denominadores explícitos (opened/expires pueden ser NULL)
print(con.execute("""SELECT count(*) n_tx, count(p.opened) n_opened, count(p.expires) n_expires,
  sum((t.ts < p.opened)::INT) n_before_open, sum((t.ts > p.expires)::INT) n_after_exp,
  sum((t.ts < p.opened)::INT)/count(p.opened) share_before_open_of_nonnull,
  sum((t.ts > p.expires)::INT)/count(p.expires) share_after_exp_of_nonnull,
  sum((t.ts < p.opened OR t.ts > p.expires)::INT) n_outside_any
  FROM tx t JOIN pr p USING(product_id)""").fetchdf().T)
print(con.execute("""SELECT ptype, count(*) n, avg((opened IS NULL)::INT) opened_null, avg((expires IS NULL)::INT) exp_null FROM pr GROUP BY 1 ORDER BY 1""").fetchdf().to_string(index=False))
