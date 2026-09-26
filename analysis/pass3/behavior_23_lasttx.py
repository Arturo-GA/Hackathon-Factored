"""pr.last_tx vs actividad real (MAX(tx.ts)) por producto activo."""
from behavior_common import connect, q
con = connect()
print(q(con, """WITH a AS (SELECT product_id, max(ts) mx, min(ts) mn FROM tx GROUP BY 1)
 SELECT count(*) n, avg((p.last_tx IS NULL)::INT) lt_null,
  median(date_diff('day', a.mx::DATE, DATE '2026-06-17')) med_days_since_real, median(date_diff('day', p.last_tx::DATE, DATE '2026-06-17')) med_days_since_lt,
  avg((abs(date_diff('day', a.mx::DATE, p.last_tx::DATE))<=1)::INT) match_1d, avg((p.last_tx < a.mn)::INT) lt_before_first_tx,
  avg((p.last_tx > a.mx)::INT) lt_after_last, avg((p.last_tx::DATE >= p.opened)::INT) lt_ge_open, corr(epoch(p.last_tx), epoch(a.mx)) corr_real
 FROM pr p JOIN a USING(product_id) WHERE p.pstatus='Active'"""))
print(q(con, """SELECT pstatus, count(*) n, avg((last_tx IS NULL)::INT) lt_null, avg((dpd IS NULL)::INT) dpd_null, sum(CASE WHEN product_id IN (SELECT DISTINCT product_id FROM tx) THEN 1 ELSE 0 END) with_tx FROM pr GROUP BY 1"""))
print(q(con, "SELECT dayofweek(ts) dw, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),2) pct FROM tx GROUP BY 1 ORDER BY 1"))
