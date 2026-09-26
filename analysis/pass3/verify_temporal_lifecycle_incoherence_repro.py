"""Verificación independiente: temporal_lifecycle_incoherence."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

# 1) tx vs opened / expires, a nivel tx (definición por fecha: ts::DATE vs DATE, y por timestamp)
print(q("""SELECT count(*) n_tx,
  sum((t.ts < p.opened)::INT) before_open_ts,
  sum((t.ts::DATE < p.opened)::INT) before_open_date,
  sum((p.expires IS NOT NULL)::INT) n_tx_with_exp,
  sum((p.ptype LIKE 'Tarjeta%')::INT) n_tx_card,
  sum((t.ts > p.expires)::INT) after_exp_ts,
  sum((t.ts::DATE > p.expires)::INT) after_exp_date,
  sum((t.ts < p.opened OR coalesce(t.ts > p.expires,false))::INT) outside
  FROM tx t JOIN pr p USING(product_id)""").T)
print(q("SELECT count(*) n_tx_total, count(p.product_id) n_match FROM tx t LEFT JOIN pr p USING(product_id)"))

# decline rate inside vs outside
print(q("""SELECT (t.ts < p.opened OR coalesce(t.ts > p.expires,false)) outside, count(*) n,
  avg((status='Declined')::INT) decl, avg((status='Approved')::INT) appr, avg(fraud::INT) fraud
  FROM tx t JOIN pr p USING(product_id) GROUP BY 1""").to_string(index=False))
# por componente
print(q("""SELECT (t.ts < p.opened) before_open, coalesce(t.ts > p.expires,false) after_exp, count(*) n,
  avg((status='Declined')::INT) decl FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False))

# 2) nivel producto
con.execute("""CREATE TEMP TABLE pa AS SELECT product_id, count(*) n, min(ts) f, max(ts) l FROM tx GROUP BY 1""")
print(q("""SELECT count(*) n_prod, avg((sum_b>0)::INT) share_prod_any_before_open FROM
  (SELECT t.product_id, sum((t.ts < p.opened)::INT) sum_b FROM tx t JOIN pr p USING(product_id) GROUP BY 1)"""))
print(q("""SELECT (p.opened >= DATE '2023-06-17') in_window, count(*) n_prod, avg(a.n) avg_tx,
  avg((a.f < p.opened)::INT) first_before_open FROM pa a JOIN pr p USING(product_id) GROUP BY 1""").to_string(index=False))
# productos abiertos en ventana: tx/día antes vs después de opened (uniformidad)
print(q("""WITH w AS (SELECT p.product_id, p.opened FROM pr p JOIN pa a USING(product_id)
     WHERE p.opened > DATE '2023-09-01' AND p.opened < DATE '2026-03-01')
  SELECT sum((t.ts < w.opened)::INT) n_before, sum((t.ts >= w.opened)::INT) n_after,
    sum(date_diff('day', DATE '2023-06-17', w.opened)) FILTER (WHERE true) dummy
  FROM tx t JOIN w USING(product_id)"""))
print(q("""WITH w AS (SELECT p.product_id, p.opened FROM pr p JOIN pa a USING(product_id)
     WHERE p.opened > DATE '2023-09-01' AND p.opened < DATE '2026-03-01')
  SELECT sum(date_diff('day', DATE '2023-06-17', opened)) days_before, sum(date_diff('day', opened, DATE '2026-06-18')) days_after FROM w"""))

# 3) last_tx vs max ts
print(q("""SELECT count(*) n, count(p.last_tx) has_lt,
  avg((p.last_tx = a.l)::INT) eq_ts, avg((p.last_tx::DATE = a.l::DATE)::INT) eq_date,
  avg((p.last_tx < p.opened)::INT) lt_before_open,
  quantile_cont(date_diff('day', a.l, p.last_tx), [0.1,0.5,0.9]) q
  FROM pa a JOIN pr p USING(product_id)""").T)

# 4) clientes: primera tx antes de registro
print(q("""WITH c AS (SELECT customer_id, min(ts) f FROM tx GROUP BY 1)
  SELECT count(*) n, count(cu.customer_id) n_match, avg((c.f < cu.registration_date)::INT) before_reg
  FROM c LEFT JOIN cu USING(customer_id)""").T)

# 5) last_updated futuro
for end in ["TIMESTAMP '2026-06-17 23:59:59'", "TIMESTAMP '2026-06-18 06:00:00'"]:
    print(end, q(f"""SELECT (SELECT avg((last_updated > {end})::INT) FROM pr) pr_fut, (SELECT max(last_updated) FROM pr) pr_max,
      (SELECT avg((last_updated > {end})::INT) FROM cu) cu_fut, (SELECT max(last_updated) FROM cu) cu_max""").to_string(index=False))

# 6) status de productos con tx; Active vencidos
print(q("""SELECT p.pstatus, count(*) n_tx FROM tx t JOIN pr p USING(product_id) GROUP BY 1""").to_string(index=False))
print(q("""SELECT pstatus, count(*) n, count(expires) n_exp, avg((expires < DATE '2026-06-17')::INT) exp_share_of_nonnull,
  sum((expires < DATE '2026-06-17')::INT)/count(*) exp_share_of_all FROM pr GROUP BY 1""").to_string(index=False))

# 7) densidad de tx antes/después de registration_date (clientes registrados dentro de la ventana)
print(q("""WITH w AS (SELECT customer_id, registration_date r FROM cu WHERE r > TIMESTAMP '2023-09-01' AND r < TIMESTAMP '2026-03-01'
     AND customer_id IN (SELECT DISTINCT customer_id FROM tx))
  SELECT (SELECT sum((t.ts < w.r)::INT) FROM tx t JOIN w USING(customer_id)) n_before,
         (SELECT sum((t.ts >= w.r)::INT) FROM tx t JOIN w USING(customer_id)) n_after,
         (SELECT sum(date_diff('day', TIMESTAMP '2023-06-17', r)) FROM w) d_before,
         (SELECT sum(date_diff('day', r, TIMESTAMP '2026-06-18')) FROM w) d_after"""))
