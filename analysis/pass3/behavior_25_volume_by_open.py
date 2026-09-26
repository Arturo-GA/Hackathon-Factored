"""¿El #tx por producto activo depende del año de apertura del producto o de registro del cliente? (debería si el generador respetara el ciclo de vida)"""
from behavior_common import connect, q
con = connect()
print(q(con, """SELECT year(p.opened) y, count(*) nprod, avg(coalesce(t.n,0)) avg_tx, var_samp(coalesce(t.n,0)) var_tx FROM pr p LEFT JOIN (SELECT product_id, count(*) n FROM tx GROUP BY 1) t USING(product_id)
  WHERE p.pstatus='Active' GROUP BY 1 ORDER BY 1"""))
print(q(con, """SELECT year(c.registration_date) y, count(*) nprod, avg(coalesce(t.n,0)) avg_tx FROM pr p JOIN cu c USING(customer_id) LEFT JOIN (SELECT product_id, count(*) n FROM tx GROUP BY 1) t USING(product_id)
  WHERE p.pstatus='Active' GROUP BY 1 ORDER BY 1"""))
