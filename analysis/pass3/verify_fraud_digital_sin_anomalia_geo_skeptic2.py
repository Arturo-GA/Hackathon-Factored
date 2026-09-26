"""Verificador escéptico: fraud_digital_sin_anomalia_geo (parte 2: sesiones, IP por sesión, sesiones mixtas, 'Mexico')."""
import sys, time; sys.path.insert(0,'analysis/pass3')
import pandas as pd
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',40); pd.set_option('display.max_rows',80)
con = connect()
t=time.time()
con.execute("""CREATE TEMP TABLE s AS SELECT session_id, count(*) ne, count(customer_id) n_ident,
  min(customer_id) c0, max(customer_id) c1, min(ip_address) ip0, max(ip_address) ip1, count(ip_address) n_ip,
  min(ip_country) k0, max(ip_country) k1, min(ip_city) city0, max(ip_city) city1, count(ip_city) n_city,
  min(ts) t0, max(ts) t1, min(ts) FILTER (WHERE customer_id IS NOT NULL) ti0, max(ts) FILTER (WHERE customer_id IS NOT NULL) ti1
  FROM de GROUP BY 1""")
print('temp s', round(time.time()-t,1),'s')
print("== E1. sesiones: IP/país/ciudad/cliente múltiples ==")
print(q(con,"""SELECT count(*) n_sess,
  count(*) FILTER (WHERE ip0<>ip1) multi_ip, count(*) FILTER (WHERE n_ip>0 AND n_ip<ne) mix_null_ip, count(*) FILTER (WHERE n_ip=0) all_null_ip,
  count(*) FILTER (WHERE k0<>k1) multi_ctry, count(*) FILTER (WHERE city0<>city1) multi_city,
  count(*) FILTER (WHERE n_city>0 AND n_city<ne) mix_null_city,
  count(*) FILTER (WHERE c0<>c1) multi_cust,
  count(*) FILTER (WHERE n_ident=0) full_anon, count(*) FILTER (WHERE n_ident=ne) full_ident, count(*) FILTER (WHERE n_ident>0 AND n_ident<ne) mixed
  FROM s""").T)
print("== E2. duración de sesión (min) y eventos por sesión, por tipo ==")
print(q(con,"""SELECT CASE WHEN n_ident=0 THEN 'anon' WHEN n_ident=ne THEN 'ident' ELSE 'mixta' END tipo, count(*) n, sum(ne) eventos,
  round(avg(ne),2) ev_med, quantile_cont(date_diff('second',t0,t1)/60.0,[0.5,0.9,0.99,1.0]) span_min
  FROM s GROUP BY 1 ORDER BY 1"""))
print("== E3. país IP en sesiones 100% anónimas (y ciudad nula) ==")
print(q(con,"""SELECT s.k0 pais, count(*) sesiones, sum(ne) eventos, round(100.0*sum(n_city)/sum(ne),2) pct_city_notnull
   FROM s WHERE n_ident=0 GROUP BY 1 ORDER BY 2 DESC"""))
print("== E4. 'Mexico' sin tilde por tipo de sesión ==")
print(q(con,"""SELECT CASE WHEN s.n_ident=0 THEN 'anon' WHEN s.n_ident=s.ne THEN 'ident' ELSE 'mixta' END tipo, d.customer_id IS NULL ev_anon, d.ip_country, count(*) n
  FROM de d JOIN s USING(session_id) GROUP BY ALL ORDER BY 1,2,3"""))
print(round(time.time()-t,1),'s')
print("== F. sesiones mixtas: eventos anónimos vs cliente identificado de la sesión ==")
print(q(con,"""SELECT count(*) anon_ev, count(*) FILTER (WHERE s.c0=s.c1) atribuibles,
  count(*) FILTER (WHERE s.c0=s.c1 AND d.ip_country=c.country) ctry_eq_cli, count(*) FILTER (WHERE s.c0=s.c1 AND d.ip_country<>c.country) ctry_neq_cli,
  count(*) FILTER (WHERE s.c0=s.c1 AND d.ip_city=c.city) city_eq, count(*) FILTER (WHERE s.c0=s.c1 AND d.ip_city<>c.city) city_neq, count(*) FILTER (WHERE s.c0=s.c1 AND d.ip_city IS NULL) city_null,
  count(*) FILTER (WHERE d.ts < s.ti0) antes_1er_ident, count(*) FILTER (WHERE d.ts > s.ti1) despues_ult_ident,
  count(*) FILTER (WHERE d.ts BETWEEN s.ti0 AND s.ti1) intercalados
  FROM de d JOIN s USING(session_id) LEFT JOIN cu c ON c.customer_id=s.c0
  WHERE d.customer_id IS NULL AND s.n_ident>0"""))
print("== F2. event_type de anónimos en sesiones mixtas vs anónimas vs identificados ==")
print(q(con,"""SELECT CASE WHEN s.n_ident=0 THEN 'anon' WHEN s.n_ident=s.ne THEN 'ident' ELSE 'mixta' END tipo, d.customer_id IS NULL ev_anon, d.event_type, count(*) n
  FROM de d JOIN s USING(session_id) GROUP BY ALL ORDER BY 1,2,4 DESC"""))
print(round(time.time()-t,1),'s')
