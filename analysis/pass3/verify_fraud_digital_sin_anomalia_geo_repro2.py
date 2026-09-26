"""Verificación (2): sesiones 100% anónimas (país/ciudad), colisiones de IP esperadas por azar (cumpleaños),
tasa de nulos inyectados, y si el dispositivo (platform/browser) es fijo por cliente o aleatorio por sesión."""
import duckdb, time
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
T0 = time.time()
def show(title, sql):
    df = con.execute(sql).df()
    print(f"\n== {title}  [{time.time()-T0:.0f}s]")
    print(df.to_string(index=False))
    return df

con.execute("""CREATE TEMP TABLE s AS SELECT session_id, min(customer_id) cid,
  count(*) ne, count(ip_city) n_city, any_value(ip_country) ctry, count(ip_address) n_ip
  FROM de GROUP BY 1""")
show("1 sesiones 100% anónimas vs con cliente: país y ciudad", """
SELECT (cid IS NULL) sesion_anon, ctry, count(*) n_sess, sum(ne) n_ev,
  count(*) FILTER (WHERE n_city>0) sess_con_ciudad, round(100.0*sum(n_city)/sum(ne),2) pct_ev_con_ciudad,
  round(100.0*sum(n_ip)/sum(ne),2) pct_ev_con_ip
FROM s GROUP BY ALL ORDER BY 1,2""")
show("2 tasa de customer_id nulo dentro de sesiones con cliente", """
SELECT count(*) n_ev, count(*) FILTER (WHERE d.customer_id IS NULL) anon, round(100.0*count(*) FILTER (WHERE d.customer_id IS NULL)/count(*),3) pct
FROM de d JOIN s USING(session_id) WHERE s.cid IS NOT NULL""")
# colisiones de IP: rango de octetos y esperado por cumpleaños n(n-1)/(2N)
o = show("3 rango de octetos de ip_address", """
WITH p AS (SELECT string_split(ip_address,'.') o FROM de WHERE ip_address IS NOT NULL)
SELECT min(o[1]::INT) o1min, max(o[1]::INT) o1max, min(o[2]::INT) o2min, max(o[2]::INT) o2max,
       min(o[3]::INT) o3min, max(o[3]::INT) o3max, min(o[4]::INT) o4min, max(o[4]::INT) o4max FROM p""").iloc[0]
N = 1
for k in range(1,5):
    N *= int(o[f'o{k}max']) - int(o[f'o{k}min']) + 1
n = con.execute("SELECT count(*) FROM s WHERE n_ip>0").fetchone()[0]
obs = con.execute("""SELECT count(*) FROM (SELECT ip_address FROM de WHERE ip_address IS NOT NULL GROUP BY 1
                     HAVING count(DISTINCT session_id)>1)""").fetchone()[0]
print(f"sesiones con IP n={n:,}; espacio N={N:,}; colisiones esperadas={n*(n-1)/(2*N):.0f}; observadas (IPs en >1 sesión)={obs}")
# dispositivo por cliente: ¿fijo o aleatorio por sesión?
show("4 diversidad de dispositivo por cliente (sesiones identificadas)", """
WITH ss AS (SELECT session_id, any_value(customer_id) cid, any_value(platform) plat, any_value(browser) brw, any_value(channel) ch
            FROM de WHERE customer_id IS NOT NULL GROUP BY 1),
c AS (SELECT cid, count(*) nsess, count(DISTINCT plat) nplat, count(DISTINCT brw) nbrw, count(DISTINCT ch) nch FROM ss GROUP BY 1)
SELECT count(*) n_cli, avg(nsess) sess, avg(nplat) plat_distintas, avg(nbrw) browsers_distintos, avg(nch) canales_distintos,
  count(*) FILTER (WHERE nsess>=5 AND nplat=1) cli_5plus_1plat, count(*) FILTER (WHERE nsess>=5) cli_5plus FROM c""")
show("5 plataformas/canales globales", """
SELECT channel, platform, count(DISTINCT session_id) n_sess FROM de WHERE customer_id IS NOT NULL GROUP BY ALL ORDER BY 3 DESC LIMIT 12""")
print(f"\nTotal {time.time()-T0:.0f}s")
