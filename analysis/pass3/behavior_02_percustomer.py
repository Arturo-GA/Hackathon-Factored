"""Tx por cliente y por producto: distribución, concentración (Gini), relación con #productos activos."""
from behavior_common import connect, q
import numpy as np
con = connect()
con.execute("""CREATE TEMP TABLE cst AS
 SELECT c.customer_id, c.segment, c.income, c.credit_score, c.country, c.occupation, c.cstatus, c.dob, c.registration_date,
   coalesce(t.n,0) ntx, coalesce(p.nprod,0) nprod, coalesce(p.nact,0) nact
 FROM cu c
 LEFT JOIN (SELECT customer_id, count(*) n FROM tx GROUP BY 1) t USING(customer_id)
 LEFT JOIN (SELECT customer_id, count(*) nprod, sum((pstatus='Active')::INT) nact FROM pr GROUP BY 1) p USING(customer_id)""")
d = q(con, "SELECT ntx, nprod, nact FROM cst")
print(d.describe(percentiles=[.1,.25,.5,.75,.9,.99]))
x = np.sort(d.ntx.values); n=len(x); cum=np.cumsum(x)
gini = (n+1-2*np.sum(cum)/cum[-1])/n
print("gini ntx:", gini, "top10% share:", x[-n//10:].sum()/x.sum(), "top1%:", x[-n//100:].sum()/x.sum())
print("corr ntx~nact:", np.corrcoef(d.ntx, d.nact)[0,1], " R2:", np.corrcoef(d.ntx, d.nact)[0,1]**2)
print(q(con, "SELECT nact, count(*) ncust, avg(ntx) avg_tx, median(ntx) med, stddev(ntx) sd, avg(ntx)/nullif(nact,0) tx_per_act FROM cst GROUP BY 1 ORDER BY 1"))
# tx por producto activo
dp = q(con, """SELECT p.ptype, count(*) nprod, avg(coalesce(t.n,0)) avg_tx, median(coalesce(t.n,0)) med, stddev(coalesce(t.n,0)) sd, min(coalesce(t.n,0)) mn, max(coalesce(t.n,0)) mx
  FROM pr p LEFT JOIN (SELECT product_id, count(*) n FROM tx GROUP BY 1) t USING(product_id) WHERE p.pstatus='Active' GROUP BY 1 ORDER BY 2 DESC""")
print(dp)
print(q(con, """SELECT n, count(*) FROM (SELECT p.product_id, coalesce(t.n,0) n FROM pr p LEFT JOIN (SELECT product_id, count(*) n FROM tx GROUP BY 1) t USING(product_id) WHERE p.pstatus='Active') GROUP BY 1 ORDER BY 1 LIMIT 40"""))
