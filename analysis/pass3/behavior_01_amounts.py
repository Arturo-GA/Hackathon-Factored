"""Montos por tipo y moneda; amount_usd vs amount/fx; forma de la distribución."""
from behavior_common import connect, q
con = connect()
print(q(con, """SELECT ttype, currency, count(*) n, min(amount) mn, quantile_cont(amount,0.1) p10, median(amount) p50, quantile_cont(amount,0.9) p90, max(amount) mx,
   count(amount_usd) n_usd, median(amount_usd) med_usd, max(amount_usd) mx_usd
   FROM tx GROUP BY 1,2 ORDER BY 1,2"""))
# ratio amount/amount_usd
print(q(con, """SELECT currency, count(*) n, median(amount/amount_usd) med_ratio, quantile_cont(amount/amount_usd,0.01) p01, quantile_cont(amount/amount_usd,0.99) p99
  FROM tx WHERE amount_usd IS NOT NULL AND amount_usd>0 GROUP BY 1"""))
print(q(con, "SELECT currency, amount_usd IS NULL usd_null, count(*) FROM tx GROUP BY 1,2 ORDER BY 1,2"))
print(q(con, "SELECT ptype, currency, count(*) FROM pr GROUP BY 1,2 ORDER BY 1,2"))
print(q(con, "SELECT country, currency, count(*) FROM cu JOIN pr USING(customer_id) GROUP BY 1,2 ORDER BY 1,2"))
