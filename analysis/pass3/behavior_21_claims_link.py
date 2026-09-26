"""¿Los montos reclamados (cp.claimed) coinciden con montos de tx del cliente (o de cualquier cliente)? ¿moneda del reclamo = moneda de sus productos?
Rango de claimed por categoría/moneda."""
from behavior_common import connect, q
con = connect()
print(q(con, "SELECT category, subcategory, count(*) n, count(claimed) n_cl, min(claimed) mn, median(claimed) med, max(claimed) mx FROM cp GROUP BY 1,2 ORDER BY 1,2 LIMIT 40"))
print(q(con, "SELECT currency, count(claimed) n, min(claimed) mn, median(claimed) med, max(claimed) mx FROM cp GROUP BY 1"))
con.execute("CREATE TEMP TABLE cl AS SELECT complaint_id, customer_id, CAST(round(claimed*100) AS BIGINT) cents FROM cp WHERE claimed IS NOT NULL")
con.execute("CREATE TEMP TABLE tc AS SELECT customer_id, CAST(round(amount*100) AS BIGINT) cents FROM tx")
print(q(con, "SELECT count(*) n_claims, count(DISTINCT CASE WHEN t.customer_id=c.customer_id THEN c.complaint_id END) match_same_cust, count(DISTINCT CASE WHEN t.cents IS NOT NULL THEN c.complaint_id END) match_any FROM cl c LEFT JOIN tc t USING(cents)"))
# esperado por azar: fracción de valores en céntimos 5000..500000 cubiertos por tx de cualquier cliente
print(q(con, "SELECT count(DISTINCT cents) n_distinct_cents_in_range, (500000-5000) range_size FROM tc WHERE cents BETWEEN 5000 AND 500000"))
print(q(con, "SELECT u.country, c.currency, count(*) n FROM cp c JOIN cu u USING(customer_id) GROUP BY 1,2 ORDER BY 1,2"))
