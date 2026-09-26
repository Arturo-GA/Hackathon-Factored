"""hunt_28: estructura de sesiones digitales (de) y rasgo por cliente con mitades por SESION (no por evento).
hunt_27 dio r split-half 0.83 en canal iOS / is_mobile y -0.34 en share de Login al partir por evento:
se comprueba si es agrupamiento por sesion (misma sesion en ambas mitades) o preferencia real del cliente.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_28_de_sessions.py
"""
import duckdb
import numpy as np
import pandas as pd
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
W = "customer_id IS NOT NULL AND hash(customer_id) % 8 = 0"
print('(1) estructura por sesion (muestra 1/8 de clientes)')
s = con.execute(f"""SELECT session_id, count(*) n, count(DISTINCT customer_id) ncust, count(DISTINCT channel) nch, count(DISTINCT platform) nplat,
   count(DISTINCT ip_address) nip, count(*) FILTER (WHERE event_type='Login') nlogin, count(*) FILTER (WHERE event_type='Logout') nlogout,
   count(*) FILTER (WHERE event_type='Error') nerr, epoch(max(ts)-min(ts))/60.0 span_min
   FROM de WHERE {W} GROUP BY 1""").df()
print('sesiones:', len(s))
print(s[['n', 'ncust', 'nch', 'nplat', 'nip', 'nlogin', 'nlogout', 'nerr', 'span_min']].describe(percentiles=[.05, .5, .95]).round(3).to_string())
print('P(nch=1)=', round((s.nch == 1).mean(), 4), ' P(nlogin=1)=', round((s.nlogin == 1).mean(), 4), ' P(nlogin=0)=', round((s.nlogin == 0).mean(), 4))
print('(2) sesiones por cliente y eventos por cliente')
c = con.execute(f"""SELECT customer_id, count(DISTINCT session_id) nsess, count(*) n, count(DISTINCT channel) nch,
   count(DISTINCT platform) nplat FROM de WHERE {W} GROUP BY 1""").df()
print(c[['nsess', 'n', 'nch', 'nplat']].describe(percentiles=[.05, .5, .95]).round(2).to_string())
print('(3) split-half por SESION')
df = con.execute(f"""SELECT customer_id, hash(session_id) % 2 half, count(*) n,
   avg(CASE WHEN channel='iOS App' THEN 1.0 ELSE 0 END) chan_ios, avg(CASE WHEN is_mobile THEN 1.0 ELSE 0 END) is_mobile,
   avg(CASE WHEN event_type='Error' THEN 1.0 ELSE 0 END) is_error, avg(CASE WHEN event_type='Login' THEN 1.0 ELSE 0 END) is_login,
   avg(ln(1+dur)) log_dur, avg(CASE WHEN platform='Windows' THEN 1.0 ELSE 0 END) plat_windows
   FROM de WHERE {W} GROUP BY 1,2""").df()
a = df[df.half == 0].set_index('customer_id'); b = df[df.half == 1].set_index('customer_id')
j = a.join(b, lsuffix='_a', rsuffix='_b', how='inner')
for k in ['chan_ios', 'is_mobile', 'plat_windows', 'is_error', 'is_login', 'log_dur']:
    m = j[f'{k}_a'].notna() & j[f'{k}_b'].notna()
    print(f'{k}: r_split_half_por_sesion={np.corrcoef(j.loc[m, k+"_a"], j.loc[m, k+"_b"])[0,1]:.4f} clientes={m.sum()}')
print('(4) canal/plataforma: ¿fijos por sesion? mezcla global')
print(con.execute(f"SELECT channel, platform, count(*) n FROM de WHERE {W} GROUP BY 1,2 ORDER BY 1,2").df().to_string())
