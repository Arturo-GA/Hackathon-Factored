"""Perfil básico: tx por cliente/producto, tipos, montos por tipo, fechas."""
from behavior_common import connect, q
con = connect()
print(q(con, "SELECT ttype, tcat, count(*) n, avg(amount) avg_amt, median(amount) med, min(amount) mn, max(amount) mx FROM tx GROUP BY 1,2 ORDER BY 1,3 DESC"))
print(q(con, "SELECT ttype, channel, count(*) n FROM tx GROUP BY 1,2 ORDER BY 1,3 DESC"))
print(q(con, "SELECT count(DISTINCT customer_id) ncust, count(DISTINCT product_id) nprod, min(ts), max(ts) FROM tx"))
print(q(con, "SELECT ptype, count(*) n, avg(bal) bal, count(DISTINCT customer_id) FROM pr GROUP BY 1 ORDER BY 2 DESC"))
print(q(con, "SELECT pstatus, count(*) FROM pr GROUP BY 1"))
