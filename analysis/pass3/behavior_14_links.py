"""(a) tx.customer_id == dueño del producto (b) segment -> credit_score/income rangos (c) mentioned_products en cc: ¿del cliente? ¿activos?
(d) contact_reason vs tenencia de productos (tarjeta) y vs productos bloqueados."""
from behavior_common import connect, q
con = connect()
print(q(con, "SELECT avg((t.customer_id=p.customer_id)::INT) same_owner, avg((t.currency=p.currency)::INT) same_cur, count(*) FROM tx t JOIN pr p USING(product_id)"))
#print(q(con, "SELECT segment, count(*) n, min(credit_score) mn, max(credit_score) mx, quantile_cont(income,[0,0.5,1]) inc FROM cu GROUP BY 1 ORDER BY 1"))
#print(q(con, "SELECT segment, country, min(income) mn, median(income) med, max(income) mx FROM cu GROUP BY 1,2 ORDER BY 2,1"))
# mentioned products
con.execute("""CREATE TEMP TABLE mp AS SELECT interaction_id, customer_id, contact_reason, cat, trim(unnest(string_split(mentioned_products, ','))) product_id FROM cc WHERE mentioned_products IS NOT NULL""")
print(q(con, """SELECT count(*) n, avg((p.product_id IS NOT NULL)::INT) found, avg((p.customer_id=m.customer_id)::INT) own, avg((p.pstatus='Active')::INT) active FROM mp m LEFT JOIN pr p USING(product_id)"""))
print(q(con, "SELECT product_id FROM mp LIMIT 5"))
print(q(con, "SELECT cat, contact_reason, count(*) n FROM cc GROUP BY 1,2 ORDER BY 1,3 DESC"))
