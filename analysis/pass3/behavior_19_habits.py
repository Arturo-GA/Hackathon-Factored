"""Hábitos por cliente: ¿el canal/ciudad/país/comercio/hora/día semana de una tx repite el de la anterior del mismo cliente más que por azar?
Compara P(igual a la anterior) observada vs esperada Σp² (marginal global) y vs permutación dentro del cliente no necesaria si iid."""
from behavior_common import connect, q
con = connect()
con.execute("CREATE TEMP TABLE s AS SELECT customer_id, product_id, ts, channel, city, country, merchant_name, mcat, hour(ts) h, dayofweek(ts) dw, status, code FROM tx WHERE hash(customer_id) % 8 = 0")
for col in ['channel', 'city', 'country', 'merchant_name', 'mcat', 'h', 'dw', 'code']:
    r = q(con, f"""WITH x AS (SELECT {col} v, lag({col}) OVER (PARTITION BY customer_id ORDER BY ts) pv FROM s),
       m AS (SELECT {col} v, count(*)*1.0/sum(count(*)) OVER () p FROM s WHERE {col} IS NOT NULL GROUP BY 1)
       SELECT (SELECT avg((v=pv)::INT) FROM x WHERE v IS NOT NULL AND pv IS NOT NULL) obs, (SELECT sum(p*p) FROM m) exp_iid""")
    o, e = r.iloc[0]
    print(f"{col:14s} P(igual anterior)={o:.4f} esperado_iid={e:.4f} ratio={o/e:.3f}")
# ciudad: para tx en el país del cliente, ¿la ciudad es la del cliente?
print(q(con, """SELECT avg((s.city=c.city)::INT) same_city_all, avg(CASE WHEN s.country=c.country THEN (s.city=c.city)::INT END) same_city_given_country FROM s JOIN cu c USING(customer_id) WHERE s.city IS NOT NULL"""))
