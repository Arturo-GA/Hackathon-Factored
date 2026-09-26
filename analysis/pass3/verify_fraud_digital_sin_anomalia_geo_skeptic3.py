"""Verificador escéptico: fraud_digital_sin_anomalia_geo (parte 3: IPs compartidas vs colisiones al azar; IP habitual por cliente)."""
import sys, time; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',40); pd.set_option('display.max_rows',80)
con = connect()
t=time.time()
print(q(con,"SELECT ip_address FROM de WHERE ip_address IS NOT NULL USING SAMPLE 8 ROWS"))
# sesión -> (cliente, ip) ; solo sesiones de cliente (incluye mixtas)
con.execute("""CREATE TEMP TABLE si AS SELECT session_id, max(customer_id) cid, max(ip_address) ip, bool_and(customer_id IS NULL) anon
  FROM de GROUP BY 1""")
print('temp si', round(time.time()-t,1),'s')
print("== H1. IPs: sesiones con IP, IPs distintas, IPs en >1 sesión, IPs con >1 cliente ==")
print(q(con,"""WITH x AS (SELECT ip, count(*) ns, count(DISTINCT cid) nc, count(*) FILTER (WHERE anon) n_anon FROM si WHERE ip IS NOT NULL GROUP BY 1)
  SELECT (SELECT count(*) FROM si WHERE ip IS NOT NULL) sess_con_ip,
         (SELECT count(*) FROM si WHERE ip IS NOT NULL AND NOT anon) sess_cli_con_ip,
         count(*) n_ip, count(*) FILTER (WHERE ns>1) ip_multi_sess, count(*) FILTER (WHERE nc>1) ip_multi_cli,
         count(*) FILTER (WHERE ns>1 AND nc<=1 AND n_anon=0) ip_misma_cli_varias_sesiones,
         max(ns) max_sess_por_ip FROM x"""))
print("== H2. IP habitual: por cliente, sesiones vs IPs distintas ==")
print(q(con,"""SELECT count(*) n_cli, sum(ns) sesiones, sum(nip) ips, round(avg(ns),2) ses_med, round(avg(nip),2) ip_med,
   count(*) FILTER (WHERE nip<ns) cli_con_ip_repetida FROM (SELECT cid, count(*) ns, count(DISTINCT ip) nip FROM si WHERE NOT anon AND ip IS NOT NULL GROUP BY 1)"""))
print("== H3. primer octeto (espacio de IPs) ==")
oct_ = q(con,"""SELECT TRY_CAST(split_part(ip,'.',1) AS INT) o1, count(*) n FROM si WHERE ip IS NOT NULL GROUP BY 1 ORDER BY 1""")
print('octetos distintos', len(oct_), 'min', oct_.o1.min(), 'max', oct_.o1.max(), 'n min/max por octeto', oct_.n.min(), oct_.n.max())
print('octetos ausentes 1..255:', sorted(set(range(0,256))-set(oct_.o1.dropna().astype(int)))[:40])
S = q(con,"SELECT count(*) n FROM si WHERE ip IS NOT NULL").n[0]
for M,lab in [(2**32,'2^32'),(len(oct_)*2**24,f'{len(oct_)} octetos x 2^24')]:
    print(f'colisiones esperadas al azar ({lab}): S^2/(2M) =', round(S*S/(2*M),1), ' S=',S)
print(round(time.time()-t,1),'s')
