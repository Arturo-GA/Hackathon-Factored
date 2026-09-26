"""Regla segmento -> ingreso (en USD equivalente con MXN=17, COP=4000, ARS=350) y -> credit_score; dispersión Poisson de tx por producto activo."""
from behavior_common import connect, q
con = connect()
print(q(con, """SELECT segment, count(*) n, min(iu) mn, quantile_cont(iu,[0.25,0.5,0.75]) q, max(iu) mx, avg((iu BETWEEN lo AND hi)::INT) in_range FROM (
  SELECT segment, income / CASE country WHEN 'México' THEN 17 WHEN 'Colombia' THEN 4000 ELSE 350 END iu,
    CASE segment WHEN 'Basic' THEN 800 WHEN 'Plus' THEN 3000 WHEN 'Premium' THEN 8000 ELSE 300 END lo,
    CASE segment WHEN 'Basic' THEN 2800 WHEN 'Plus' THEN 10500 WHEN 'Premium' THEN 28000 ELSE 1050 END hi FROM cu WHERE income IS NOT NULL) GROUP BY 1 ORDER BY 1"""))
print(q(con, "SELECT segment, avg(credit_score) m, stddev(credit_score) sd, min(credit_score) mn, max(credit_score) mx, avg((credit_score IS NULL)::INT) nul FROM cu GROUP BY 1 ORDER BY 1"))
print(q(con, """SELECT avg(n) mean, var_samp(n) var, var_samp(n)/avg(n) dispersion, count(*) nprod FROM (SELECT p.product_id, count(t.transaction_id) n FROM pr p LEFT JOIN tx t USING(product_id) WHERE p.pstatus='Active' GROUP BY 1)"""))
print(q(con, "SELECT (SELECT count(*) FROM tx)*1.0/(SELECT count(*) FROM pr WHERE pstatus='Active') tx_per_active"))
