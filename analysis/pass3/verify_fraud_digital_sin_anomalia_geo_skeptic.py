"""Verificador escéptico: fraud_digital_sin_anomalia_geo (parte 1: conteos base, país/ciudad IP vs cliente)."""
import sys, time; sys.path.insert(0,'analysis/pass3')
import pandas as pd
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30); pd.set_option('display.max_rows',80)
con = connect()
t=time.time()
print("== A. conteos base de ==")
print(q(con,"""SELECT count(*) n, count(customer_id) ident, count(*)-count(customer_id) anon,
  count(*) FILTER (WHERE customer_id='') cid_empty,
  count(*) FILTER (WHERE ip_country IS NULL) ipc_null, count(*) FILTER (WHERE ip_country='') ipc_empty,
  count(*) FILTER (WHERE ip_address IS NULL) ip_null, count(*) FILTER (WHERE ip_address='') ip_empty,
  count(*) FILTER (WHERE ip_city IS NULL) city_null, count(*) FILTER (WHERE ip_city='') city_empty,
  count(*) FILTER (WHERE session_id IS NULL) sess_null, count(*) FILTER (WHERE ts IS NULL) ts_null
  FROM de""").T); print(round(time.time()-t,1),'s')
print("== B. identificados: ip vs cliente (LEFT JOIN para huérfanos) ==")
print(q(con,"""SELECT count(*) n, count(c.customer_id) with_cu,
  count(*) FILTER (WHERE d.ip_country = c.country) ctry_eq, count(*) FILTER (WHERE d.ip_country <> c.country) ctry_neq,
  count(*) FILTER (WHERE d.ip_country IS NULL) ipc_null,
  count(*) FILTER (WHERE d.ip_city = c.city) city_eq, count(*) FILTER (WHERE d.ip_city <> c.city) city_neq,
  count(*) FILTER (WHERE d.ip_city IS NULL) city_null,
  count(*) FILTER (WHERE d.ip_address IS NULL) ip_null
  FROM de d LEFT JOIN cu c ON c.customer_id=d.customer_id WHERE d.customer_id IS NOT NULL""").T); print(round(time.time()-t,1),'s')
print("== C. ip_country por anónimo/identificado ==")
print(q(con,"""SELECT customer_id IS NULL anon, ip_country, count(*) n FROM de GROUP BY ALL ORDER BY 1,3 DESC"""))
print("== D. cu.country ==")
print(q(con,"SELECT country, count(*) n FROM cu GROUP BY 1 ORDER BY 2 DESC"))
print("== D2. ip_city nula: ¿depende de algo? (identificados) ==")
print(q(con,"""SELECT ip_country, count(*) n, round(100.0*count(*) FILTER (WHERE ip_city IS NULL)/count(*),2) pct_city_null,
   round(100.0*count(*) FILTER (WHERE ip_address IS NULL)/count(*),2) pct_ip_null FROM de GROUP BY 1 ORDER BY 2 DESC"""))
print(round(time.time()-t,1),'s')
