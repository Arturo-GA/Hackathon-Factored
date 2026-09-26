"""Verificador escéptico (ronda 2) fraud_digital_sin_anomalia_geo — parte A:
regla ip_country/ip_city = cliente, sesiones (IP/país/ciudad/dispositivo), 'Mexico', atribución por sesión, IPs vs azar."""
import sys, time; sys.path.insert(0, 'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 80)
con = connect()
t0 = time.time()
def T(m): print(f'\n[{time.time()-t0:.0f}s] == {m} ==', flush=True)

T('A1. conteos base de')
print(q(con, """SELECT count(*) n, count(customer_id) ident, count(*) FILTER (WHERE customer_id='') cid_empty,
  count(ip_address) ip_nn, count(ip_country) ipc_nn, count(ip_city) city_nn, count(session_id) sess_nn,
  count(*) FILTER (WHERE ip_country<>trim(ip_country) OR ip_city<>trim(ip_city)) espacios,
  min(ts) ts_min, max(ts) ts_max FROM de""").T)

T('A2. identificados: IP vs cliente (LEFT JOIN => huérfanos)')
a2 = q(con, """SELECT count(*) n, count(c.customer_id) con_cu,
  count(*) FILTER (WHERE d.ip_country = c.country) ctry_eq, count(*) FILTER (WHERE d.ip_country <> c.country) ctry_neq,
  count(*) FILTER (WHERE d.ip_country IS NULL) ctry_null,
  count(*) FILTER (WHERE d.ip_city = c.city) city_eq, count(*) FILTER (WHERE d.ip_city <> c.city) city_neq,
  count(*) FILTER (WHERE d.ip_city IS NULL) city_null, count(*) FILTER (WHERE d.ip_address IS NULL) ip_null,
  count(*) FILTER (WHERE d.ip_city IS NULL AND d.ip_address IS NULL) ambos_null
  FROM de d LEFT JOIN cu c ON c.customer_id = d.customer_id WHERE d.customer_id IS NOT NULL""")
print(a2.T)
r = a2.iloc[0]
print('pct city null', round(100*r.city_null/r.n, 2), 'pct ip null', round(100*r.ip_null/r.n, 2),
      'ambos null obs', int(r.ambos_null), 'esperado si indep', round(r.city_null*r.ip_null/r.n))

T('A3. ip_country x anon y cu.country')
print(q(con, "SELECT customer_id IS NULL anon, ip_country, count(*) n, count(ip_city) city_nn FROM de GROUP BY ALL ORDER BY 1,2"))
print(q(con, "SELECT country, count(*) n FROM cu GROUP BY 1 ORDER BY 2 DESC"))

T('B0. tabla de sesiones')
con.execute("""CREATE TEMP TABLE s AS SELECT session_id, count(*) ne, count(customer_id) ni,
  min(customer_id) c0, max(customer_id) c1, min(ip_address) ip0, max(ip_address) ip1, count(ip_address) n_ip,
  min(ip_country) k0, max(ip_country) k1, min(ip_city) city0, max(ip_city) city1, count(ip_city) n_city,
  min(platform) pl0, max(platform) pl1, min(browser) br0, max(browser) br1, min(channel) ch0, max(channel) ch1,
  min(is_mobile::INT) m0, max(is_mobile::INT) m1,
  count(*) FILTER (WHERE ip_country='Mexico') n_mex, count(*) FILTER (WHERE ip_country='México') n_mex_t,
  min(ts) t_0, max(ts) t_1
  FROM de GROUP BY 1""")
print('sesiones', q(con, 'SELECT count(*) n FROM s').n[0])

T('B1. sesiones: >1 IP/país/ciudad/cliente/dispositivo')
print(q(con, """SELECT count(*) n_sess,
  count(*) FILTER (WHERE ip0<>ip1) multi_ip, count(*) FILTER (WHERE k0<>k1) multi_ctry, count(*) FILTER (WHERE city0<>city1) multi_city,
  count(*) FILTER (WHERE c0<>c1) multi_cust, count(*) FILTER (WHERE pl0<>pl1) multi_platform, count(*) FILTER (WHERE br0<>br1) multi_browser,
  count(*) FILTER (WHERE ch0<>ch1) multi_channel, count(*) FILTER (WHERE m0<>m1) multi_mobile,
  count(*) FILTER (WHERE ni=0) full_anon, count(*) FILTER (WHERE ni=ne) full_ident, count(*) FILTER (WHERE ni>0 AND ni<ne) mixtas,
  count(*) FILTER (WHERE n_ip=0) sin_ip, count(*) FILTER (WHERE ne=1) de_1_evento
  FROM s""").T)

T('B2. Mexico sin tilde / con tilde por tipo de sesión; sesiones anónimas: país y ciudad')
print(q(con, """SELECT CASE WHEN ni=0 THEN 'anon' WHEN ni=ne THEN 'ident' ELSE 'mixta' END tipo, count(*) sesiones, sum(ne) eventos,
  sum(ne-ni) ev_anon, sum(n_mex) ev_Mexico, sum(n_mex_t) ev_México, sum(n_city) city_nn, round(avg(ne),2) ev_x_sesion,
  round(median(date_diff('second', t_0, t_1)/60.0),1) med_min
  FROM s GROUP BY 1 ORDER BY 1"""))
print(q(con, """SELECT k0 pais, count(*) sesiones, sum(ne) eventos, sum(n_city) city_nn FROM s WHERE ni=0 GROUP BY 1 ORDER BY 2 DESC"""))

T('B3. atribución de anónimos por sesión (cobertura real)')
b3 = q(con, """SELECT (SELECT count(*) FROM de) total, (SELECT count(customer_id) FROM de) ident,
   sum(ne-ni) FILTER (WHERE ni>0 AND c0=c1) atrib, sum(ne-ni) FILTER (WHERE ni>0 AND c0<>c1) no_atrib_multi,
   sum(ne-ni) FILTER (WHERE ni=0) anon_puro,
   count(*) FILTER (WHERE ni>0 AND ni<ne AND (k0<>k1 OR city0<>city1)) mixtas_inconsist
   FROM s""")
print(b3.T); r = b3.iloc[0]
anon = r.total - r.ident
print(f'anónimos {anon:,.0f}; atribuibles {r.atrib:,.0f} = {100*r.atrib/anon:.1f}% de anónimos; '
      f'+{100*r.atrib/r.ident:.2f}% relativo a identificados; cobertura {100*r.ident/r.total:.2f}% -> {100*(r.ident+r.atrib)/r.total:.2f}%')

T('C1. IPs: una por sesión -> colisiones entre sesiones vs azar (cumpleaños)')
con.execute("""CREATE TEMP TABLE si AS SELECT session_id, ip0 ip, CASE WHEN ni>0 THEN c1 END cid, k0 k FROM s WHERE ip0 IS NOT NULL""")
oc = q(con, """SELECT min(TRY_CAST(split_part(ip,'.',1) AS INT)) o1min, max(TRY_CAST(split_part(ip,'.',1) AS INT)) o1max,
   count(DISTINCT split_part(ip,'.',1)) o1n, min(TRY_CAST(split_part(ip,'.',4) AS INT)) o4min, max(TRY_CAST(split_part(ip,'.',4) AS INT)) o4max,
   count(DISTINCT split_part(ip,'.',2)) o2n, count(DISTINCT split_part(ip,'.',3)) o3n, count(DISTINCT split_part(ip,'.',4)) o4n,
   count(*) FILTER (WHERE ip NOT SIMILAR TO '[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+') no_ipv4 FROM si""")
print(oc.T)
x = q(con, """WITH g AS (SELECT ip, count(*) ns, count(cid) ns_cli, count(DISTINCT cid) nc, count(DISTINCT k) nk FROM si GROUP BY 1)
  SELECT count(*) n_ip, sum(ns) sesiones, count(*) FILTER (WHERE ns>1) ip_multi_sesion, sum(ns*(ns-1)/2) pares,
    count(*) FILTER (WHERE nc>1) ip_multi_cliente, count(*) FILTER (WHERE ns_cli>1 AND nc=1) ip_mismo_cliente_rep,
    count(*) FILTER (WHERE ns>1 AND nk=1) multi_mismo_pais, max(ns) max_ses FROM g""")
print(x.T)
S = int(x.sesiones[0]); o = oc.iloc[0]
M = int(o.o1n) * int(o.o2n) * int(o.o3n) * int(o.o4n)
print(f'espacio IP efectivo M={M:,} (octetos {o.o1n}x{o.o2n}x{o.o3n}x{o.o4n}); pares esperados al azar S^2/(2M) = {S*S/(2*M):.1f}; observados {int(x.pares[0])}')
# solo sesiones de clientes
xc = q(con, """WITH g AS (SELECT ip, count(*) ns, count(DISTINCT cid) nc FROM si WHERE cid IS NOT NULL GROUP BY 1)
  SELECT count(*) n_ip_cli, sum(ns) ses_cli, count(*) FILTER (WHERE nc>1) ip_2cli, count(*) FILTER (WHERE ns>1 AND nc=1) ip_mismo_cli FROM g""")
print(xc.T)
Sc = int(xc.ses_cli[0])
print(f'IPs compartidas por 2 clientes: obs {int(xc.ip_2cli[0])} vs esperado al azar {Sc*Sc/(2*M):.1f}')
# distintos ip_address entre eventos identificados (definición del hallazgo, sin NULL)
print(q(con, "SELECT count(DISTINCT ip_address) n_ip_ident_eventos FROM de WHERE customer_id IS NOT NULL"))

T('C2. por cliente: sesiones vs IPs distintas / plataformas / navegadores (¿dispositivo habitual?)')
con.execute("""CREATE TEMP TABLE sc AS SELECT session_id, c1 cid, ip0 ip, pl0 pl, br0 br, m0 mob, ch0 ch FROM s WHERE ni>0 AND c0=c1""")
print(q(con, """WITH c AS (SELECT cid, count(*) ns, count(ip) ns_ip, count(DISTINCT ip) nip, count(DISTINCT pl) npl, count(DISTINCT br) nbr,
      count(DISTINCT ch) nch FROM sc GROUP BY 1)
  SELECT count(*) clientes, round(avg(ns),2) ses_med, sum(ns_ip) ses_con_ip, sum(nip) ips, count(*) FILTER (WHERE nip<ns_ip) cli_repite_ip,
     round(avg(npl),3) plat_dist_med, round(avg(nbr),3) nav_dist_med, round(avg(nch),3) canal_dist_med FROM c"""))
# esperado de plataformas distintas si se asignan al azar por sesión (con la marginal global)
pm = q(con, "SELECT pl, count(*) n FROM sc GROUP BY 1")
p = (pm.n / pm.n.sum()).values
nsd = q(con, "SELECT ns, count(*) k FROM (SELECT cid, count(*) ns FROM sc GROUP BY 1) GROUP BY 1")
exp_npl = sum(r.k * sum(1 - (1 - pi) ** r.ns for pi in p) for r in nsd.itertuples()) / nsd.k.sum()
print('plataformas:', dict(zip(pm.pl, pm.n)), '| distintas esperadas al azar por cliente', round(exp_npl, 3))
print(f'[{time.time()-t0:.0f}s] fin')
