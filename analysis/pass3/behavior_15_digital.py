"""Eventos digitales vs transacciones: (a) de.product_id pertenece al cliente? (b) ¿hay eventos digitales del cliente
cerca (±1h/±1d) de sus tx por App/Web vs POS/ATM? (muestra de clientes por hash)."""
from behavior_common import connect, q
con = connect()
print(q(con, "SELECT event_type, event_category, channel, count(*) n, count(product_id) n_prod FROM de GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 25"))
print(q(con, """SELECT count(*) n, avg((p.product_id IS NOT NULL)::INT) found, avg((p.customer_id=d.customer_id)::INT) own FROM (SELECT * FROM de WHERE product_id IS NOT NULL AND customer_id IS NOT NULL USING SAMPLE 200000) d LEFT JOIN pr p USING(product_id)"""))
con.execute("CREATE TEMP TABLE sc AS SELECT customer_id FROM cu WHERE hash(customer_id) % 20 = 0")
con.execute("CREATE TEMP TABLE sde AS SELECT d.customer_id, d.ts, d.event_type, d.channel FROM de d JOIN sc USING(customer_id)")
con.execute("CREATE TEMP TABLE stx AS SELECT t.transaction_id, t.customer_id, t.ts, t.channel, t.ttype FROM tx t JOIN sc USING(customer_id)")
print(q(con, "SELECT (SELECT count(*) FROM sc) ncust, (SELECT count(*) FROM sde) nde, (SELECT count(*) FROM stx) ntx"))
for w in ['1 hour', '1 day']:
    print(w, q(con, f"""SELECT t.channel, count(DISTINCT t.transaction_id) n,
      count(DISTINCT CASE WHEN d.customer_id IS NOT NULL THEN t.transaction_id END)*1.0/count(DISTINCT t.transaction_id) pct_with_event
      FROM stx t LEFT JOIN sde d ON d.customer_id=t.customer_id AND d.ts BETWEEN t.ts - INTERVAL {w} AND t.ts + INTERVAL {w}
      GROUP BY 1 ORDER BY 1"""))
# eventos de tipo transacción/pago en digital vs tx
print(q(con, "SELECT event_type, count(*) FROM sde GROUP BY 1 ORDER BY 2 DESC LIMIT 20"))
