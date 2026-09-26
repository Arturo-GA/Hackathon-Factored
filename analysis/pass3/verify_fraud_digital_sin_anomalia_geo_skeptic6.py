"""Verificador escéptico: fraud_digital_sin_anomalia_geo (parte 6: product_id de eventos de otro cliente; sesiones anónimas con ciudad)."""
import sys, time; sys.path.insert(0,'analysis/pass3')
import pandas as pd
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',40)
con = connect()
print(q(con,"""SELECT d.customer_id ev_cli, d.product_id, p.customer_id dueño_prod, p.ptype, pc.country pais_dueño, c.country pais_ev
  FROM (SELECT * FROM de WHERE product_id IS NOT NULL AND customer_id IS NOT NULL LIMIT 5) d
  JOIN pr p USING(product_id) JOIN cu pc ON pc.customer_id=p.customer_id JOIN cu c ON c.customer_id=d.customer_id"""))
print(q(con,"""SELECT round(100.0*count(*) FILTER (WHERE pc.country=c.country)/count(*),1) pct_mismo_pais_dueño, count(*) n
  FROM de d JOIN pr p USING(product_id) JOIN cu pc ON pc.customer_id=p.customer_id JOIN cu c ON c.customer_id=d.customer_id
  WHERE d.customer_id IS NOT NULL"""))
print(q(con,"""WITH s AS (SELECT session_id, count(*) ne, count(customer_id) ni, count(ip_city) nc, max(ip_country) k FROM de GROUP BY 1)
  SELECT k, count(*) sesiones_anon_con_ciudad, sum(ne) eventos FROM s WHERE ni=0 AND nc>0 GROUP BY 1"""))
