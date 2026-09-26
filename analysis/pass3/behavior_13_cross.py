"""(a) ¿Clientes con fraude/rechazos tienen más productos Blocked/Suspended? (b) volumen de contactos/reclamos/eventos vs #tx
(c) tx antes del registro del cliente (d) Pending/Reversed seguidos de tx 'gemela' (mismo producto y monto) (e) pares Transfer/Deposit mismo monto y ts."""
from behavior_common import connect, q
import numpy as np
con = connect()
con.execute("""CREATE TEMP TABLE ct AS SELECT customer_id, count(*) ntx, sum(fraud::INT) nfraud, sum((status='Declined')::INT) ndecl FROM tx GROUP BY 1""")
con.execute("""CREATE TEMP TABLE cp2 AS SELECT customer_id, count(*) nprod, sum((pstatus='Blocked')::INT) nblk, sum((pstatus='Suspended')::INT) nsus, sum((pstatus='Closed')::INT) ncl, sum((pstatus='Active')::INT) nact FROM pr GROUP BY 1""")
print(q(con, """SELECT (ct.nfraud>0) has_fraud, count(*) ncust, avg(p.nblk*1.0/p.nprod) sh_blk, avg((p.nblk>0)::INT) any_blk, avg(p.nsus*1.0/p.nprod) sh_sus, avg(p.nact) nact
   FROM ct JOIN cp2 p USING(customer_id) GROUP BY 1"""))
print(q(con, """SELECT least(ct.ndecl,5) ndecl, count(*) ncust, avg(p.nblk*1.0/p.nprod) sh_blk, avg((p.nblk>0)::INT) any_blk, avg(p.nact) nact, avg(ct.ntx) ntx
   FROM ct JOIN cp2 p USING(customer_id) GROUP BY 1 ORDER BY 1"""))
# blocked share among customers with same nact, split by fraud
print(q(con, """SELECT p.nact, (ct.nfraud>0) f, count(*) n, avg((p.nblk>0)::INT) any_blk FROM ct JOIN cp2 p USING(customer_id) WHERE p.nact BETWEEN 1 AND 4 GROUP BY 1,2 ORDER BY 1,2"""))
# volumen cruzado
con.execute("CREATE TEMP TABLE ccn AS SELECT customer_id, count(*) ncc FROM cc GROUP BY 1")
con.execute("CREATE TEMP TABLE cpn AS SELECT customer_id, count(*) ncp FROM cp GROUP BY 1")
con.execute("CREATE TEMP TABLE den AS SELECT customer_id, count(*) nde FROM de WHERE customer_id IS NOT NULL GROUP BY 1")
d = q(con, """SELECT c.customer_id, coalesce(ct.ntx,0) ntx, coalesce(p.nact,0) nact, coalesce(p.nprod,0) nprod, coalesce(ccn.ncc,0) ncc, coalesce(cpn.ncp,0) ncp, coalesce(den.nde,0) nde
  FROM cu c LEFT JOIN ct USING(customer_id) LEFT JOIN cp2 p USING(customer_id) LEFT JOIN ccn USING(customer_id) LEFT JOIN cpn USING(customer_id) LEFT JOIN den USING(customer_id)""")
print(d.drop(columns='customer_id').corr(method='spearman').round(3))
print(d.groupby(d.nprod.clip(upper=6))[['ncc','ncp','nde','ntx']].mean().round(2))
# tx antes del registro del cliente
print(q(con, """SELECT count(*) n, avg((t.ts < c.registration_date)::INT) before_reg, avg((t.ts::DATE < c.dob)::INT) before_birth FROM tx t JOIN cu c USING(customer_id)"""))
print(q(con, "SELECT min(registration_date), max(registration_date), min(dob), max(dob) FROM cu"))
print(q(con, "SELECT avg((p.opened < c.registration_date::DATE)::INT) prod_before_reg FROM pr p JOIN cu c USING(customer_id)"))
# gemelas: Pending/Reversed/Declined seguido por tx mismo producto y mismo monto
print(q(con, """WITH s AS (SELECT product_id, status, amount, ts, lead(amount) OVER (PARTITION BY product_id ORDER BY ts) na, lead(ts) OVER (PARTITION BY product_id ORDER BY ts) nts FROM tx)
   SELECT status, count(*) n, avg((abs(na-amount)<0.01)::INT) next_same_amt, avg((epoch(nts-ts)<3600)::INT) next_within_1h FROM s GROUP BY 1"""))
# pares mismo ts y mismo monto entre clientes distintos
print(q(con, """SELECT count(*) FROM (SELECT ts, amount, count(*) k, count(DISTINCT customer_id) nc FROM tx GROUP BY 1,2 HAVING count(*)>1)"""))
print(q(con, """SELECT count(*) npairs_ts FROM (SELECT ts FROM tx GROUP BY 1 HAVING count(*)>1)"""))
