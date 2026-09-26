"""Verificación independiente (reintento): fraud_digital_sin_anomalia_geo.
Secciones (argumento de línea de comandos, por defecto todas):
  A  ip_country / ip_city de eventos identificados vs país / ciudad del cliente (cu)
  B  sesiones: >1 IP / país / ciudad / cliente; tipos de sesión (100% anónima, 100% identificada, mixta)
  C  IPs: distintas, compartidas entre clientes, IP por sesión, colisiones esperadas por azar
  D  eventos anónimos: atribuibles por sesión; variante 'Mexico'; tasa de customer_id nulo en sesiones con cliente
  E  tx App/Web: evento digital del mismo cliente en ±1h/±24h (ASOF, población completa) vs placebo desplazado
  F  eventos tras un fraude con IP de otro país; tx fraude fuera del país vs IP
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_fraud_digital_sin_anomalia_geo_repro_r2.py A B
"""
import sys, time, math
import duckdb

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
T0 = time.time()
SECS = [a.upper() for a in sys.argv[1:]] or list('ABCDEF')


def show(title, sql):
    df = con.execute(sql).df()
    print(f"\n== {title}  [{time.time()-T0:.0f}s]")
    print(df.to_string(index=False))
    return df


# ---------------------------------------------------------------- A
if 'A' in SECS:
    show("A1 eventos identificados vs cliente (LEFT JOIN cu)", """
    SELECT count(*) n_ident, count(c.customer_id) con_cliente_en_cu,
      count(*) FILTER (WHERE d.ip_country IS NULL) ipc_nulo,
      count(*) FILTER (WHERE d.ip_country = c.country) pais_igual,
      count(*) FILTER (WHERE d.ip_country <> c.country) pais_distinto,
      count(*) FILTER (WHERE d.ip_city IS NULL) ciudad_ip_nula,
      count(*) FILTER (WHERE d.ip_city IS NOT NULL AND c.city IS NULL) ciudad_cli_nula,
      count(*) FILTER (WHERE d.ip_city = c.city) ciudad_igual,
      count(*) FILTER (WHERE d.ip_city <> c.city) ciudad_distinta,
      count(*) FILTER (WHERE d.ip_address IS NULL) ip_nula
    FROM de d LEFT JOIN cu c ON c.customer_id = d.customer_id
    WHERE d.customer_id IS NOT NULL""")
    show("A2 ip_country por evento anónimo/identificado", """
    SELECT (customer_id IS NULL) ev_anon, ip_country, count(*) n,
      round(100.0*count(*) FILTER (WHERE ip_city IS NULL)/count(*),2) pct_ciudad_nula,
      round(100.0*count(*) FILTER (WHERE ip_address IS NULL)/count(*),2) pct_ip_nula
    FROM de GROUP BY ALL ORDER BY 1, 3 DESC""")
    # base de comparación: si ip_city fuera aleatoria dentro del país, ¿qué % coincidiría por azar?
    show("A3 ciudades por país en cu (azar esperado de coincidencia = sum p^2)", """
    WITH x AS (SELECT country, city, count(*) n FROM cu GROUP BY ALL),
    y AS (SELECT country, city, n, n*1.0/sum(n) OVER (PARTITION BY country) p FROM x)
    SELECT country, count(*) n_ciudades, round(100*sum(p*p),1) pct_azar_misma_ciudad FROM y GROUP BY 1 ORDER BY 1""")

# ---------------------------------------------------------------- B (+ tabla de sesiones para C, D)
need_s = any(s in SECS for s in 'BCD')
if need_s:
    con.execute("""CREATE TEMP TABLE s AS
    SELECT session_id, count(*) ne, count(customer_id) n_id,
      min(customer_id) c0, max(customer_id) c1,
      min(ip_address) ip0, max(ip_address) ip1, count(ip_address) n_ipnn,
      min(ip_country) k0, max(ip_country) k1,
      min(ip_city) ci0, max(ip_city) ci1, count(ip_city) n_citynn,
      count(*) FILTER (WHERE ip_country = 'Mexico') n_mex_sin,
      count(*) FILTER (WHERE ip_country = 'México') n_mex_con,
      min(ts) t0, max(ts) t1
    FROM de GROUP BY 1""")
    print(f"\n(temp s creada) [{time.time()-T0:.0f}s]")

if 'B' in SECS:
    show("B1 sesiones", """
    SELECT count(*) n_sesiones, count(*) FILTER (WHERE session_id IS NULL) sesion_nula,
      count(*) FILTER (WHERE ip0 <> ip1) multi_ip,
      count(*) FILTER (WHERE k0 <> k1) multi_pais,
      count(*) FILTER (WHERE ci0 <> ci1) multi_ciudad,
      count(*) FILTER (WHERE c0 <> c1) multi_cliente,
      count(*) FILTER (WHERE n_ipnn > 0 AND n_ipnn < ne) mezcla_ip_nula,
      count(*) FILTER (WHERE n_id = 0) s_100_anon,
      count(*) FILTER (WHERE n_id = ne) s_100_ident,
      count(*) FILTER (WHERE n_id > 0 AND n_id < ne) s_mixta
    FROM s""")
    show("B2 duración de sesión (min) y eventos por sesión", """
    SELECT CASE WHEN n_id=0 THEN '100_anon' WHEN n_id=ne THEN '100_ident' ELSE 'mixta' END tipo,
      count(*) n_ses, sum(ne) n_ev, round(avg(ne),2) ev_por_ses,
      round(quantile_cont(date_diff('second', t0, t1)/60.0, 0.5),1) p50_min,
      round(quantile_cont(date_diff('second', t0, t1)/60.0, 0.99),1) p99_min,
      round(max(date_diff('second', t0, t1)/60.0),1) max_min
    FROM s GROUP BY 1 ORDER BY 1""")

# ---------------------------------------------------------------- C
if 'C' in SECS:
    show("C1 IPs en eventos identificados (IP no nula)", """
    WITH ip AS (SELECT ip_address, min(customer_id) cmin, max(customer_id) cmax,
                       count(DISTINCT customer_id) nc, count(DISTINCT session_id) ns
                FROM de WHERE customer_id IS NOT NULL AND ip_address IS NOT NULL GROUP BY 1)
    SELECT count(*) n_ips, count(*) FILTER (WHERE nc >= 2) ips_2mas_clientes, max(nc) max_clientes_por_ip,
      count(*) FILTER (WHERE ns >= 2) ips_2mas_sesiones,
      count(*) FILTER (WHERE ns >= 2 AND nc = 1) ips_mismo_cliente_2mas_sesiones
    FROM ip""")
    show("C2 IP como atributo de sesión (todas las sesiones con IP)", """
    WITH x AS (SELECT ip0 ip, count(*) ns FROM s WHERE ip0 IS NOT NULL GROUP BY 1)
    SELECT (SELECT count(*) FROM s WHERE ip0 IS NOT NULL) sesiones_con_ip, count(*) ips_distintas,
           count(*) FILTER (WHERE ns >= 2) ips_en_2mas_sesiones, sum(ns) FILTER (WHERE ns >= 2) sesiones_en_ip_repetida
    FROM x""")
    show("C3 IPs distintas por cliente vs sesiones por cliente", """
    WITH c AS (SELECT c0 cid, count(*) ns, count(DISTINCT ip0) nip FROM s
               WHERE c0 IS NOT NULL AND c0 = c1 AND ip0 IS NOT NULL GROUP BY 1)
    SELECT count(*) n_clientes, sum(ns) sesiones, sum(nip) ips_distintas, round(avg(ns),2) ses_por_cli,
           count(*) FILTER (WHERE nip < ns) cli_con_ip_repetida FROM c""")
    # espacio de IPs para colisiones al azar (cumpleaños)
    o = con.execute("""WITH p AS (SELECT string_split(ip0, '.') o FROM s WHERE ip0 IS NOT NULL)
      SELECT min(o[1]::INT), max(o[1]::INT), count(DISTINCT o[1]::INT), min(o[2]::INT), max(o[2]::INT),
             min(o[3]::INT), max(o[3]::INT), min(o[4]::INT), max(o[4]::INT) FROM p""").fetchone()
    print("octetos: o1 min/max/distintos", o[0:3], "o2", o[3:5], "o3", o[5:7], "o4", o[7:9])
    N = o[2] * (o[4]-o[3]+1) * (o[6]-o[5]+1) * (o[8]-o[7]+1)
    S = con.execute("SELECT count(*) FROM s WHERE ip0 IS NOT NULL").fetchone()[0]
    Sid = con.execute("SELECT count(*) FROM s WHERE ip0 IS NOT NULL AND c0 IS NOT NULL").fetchone()[0]
    print(f"espacio N={N:,}; sesiones con IP S={S:,} -> colisiones esperadas al azar S^2/2N = {S*S/(2*N):,.0f}")
    print(f"sesiones identificadas con IP Sid={Sid:,} -> pares de sesiones con misma IP esperados = {Sid*Sid/(2*N):,.0f}"
          f" (casi todos de clientes distintos)")

# ---------------------------------------------------------------- D
if 'D' in SECS:
    show("D1 eventos anónimos según su sesión", """
    SELECT count(*) ev_anon,
      count(*) FILTER (WHERE s.c0 IS NOT NULL AND s.c0 = s.c1) en_sesion_1_cliente,
      round(100.0*count(*) FILTER (WHERE s.c0 IS NOT NULL AND s.c0 = s.c1)/count(*),2) pct_atribuible,
      count(*) FILTER (WHERE s.c0 IS NOT NULL AND s.c0 <> s.c1) en_sesion_multi_cliente,
      count(*) FILTER (WHERE s.c0 IS NULL) en_sesion_100_anon
    FROM de d JOIN s USING (session_id) WHERE d.customer_id IS NULL""")
    show("D2 tasa de customer_id nulo dentro de sesiones con algún cliente", """
    SELECT sum(ne) ev, sum(ne - n_id) ev_anon, round(100.0*sum(ne - n_id)/sum(ne),3) pct_nulo
    FROM s WHERE c0 IS NOT NULL""")
    show("D3 'Mexico' / 'México' por tipo de sesión (eventos)", """
    SELECT CASE WHEN n_id=0 THEN '100_anon' WHEN n_id=ne THEN '100_ident' ELSE 'mixta' END tipo,
      sum(n_mex_sin) ev_Mexico_sin_tilde, sum(n_mex_con) ev_Mexico_con_tilde,
      count(*) FILTER (WHERE n_mex_sin > 0) ses_con_Mexico_sin_tilde
    FROM s GROUP BY 1 ORDER BY 1""")
    show("D4 sesiones 100% anónimas: país IP, % ciudad no nula", """
    SELECT k0 pais, count(*) sesiones, sum(ne) eventos, round(100.0*sum(n_citynn)/sum(ne),2) pct_ev_con_ciudad,
      round(100.0*sum(n_ipnn)/sum(ne),2) pct_ev_con_ip
    FROM s WHERE n_id = 0 GROUP BY 1 ORDER BY 2 DESC""")
    show("D5 eventos anónimos atribuidos por sesión: coinciden con país/ciudad del cliente atribuido", """
    SELECT count(*) n, count(*) FILTER (WHERE d.ip_country = c.country) pais_igual,
      count(*) FILTER (WHERE d.ip_city = c.city) ciudad_igual, count(*) FILTER (WHERE d.ip_city <> c.city) ciudad_distinta,
      count(*) FILTER (WHERE d.ip_city IS NULL) ciudad_nula
    FROM de d JOIN s USING (session_id) JOIN cu c ON c.customer_id = s.c0
    WHERE d.customer_id IS NULL AND s.c0 = s.c1""")
    show("D6 cobertura: eventos identificados originales vs añadidos por sesión", """
    SELECT (SELECT count(*) FROM de WHERE customer_id IS NOT NULL) ident,
           (SELECT sum(ne - n_id) FROM s WHERE c0 IS NOT NULL AND c0 = c1) anon_atribuibles,
           round(100.0*(SELECT sum(ne - n_id) FROM s WHERE c0 IS NOT NULL AND c0 = c1)
                 /(SELECT count(*) FROM de WHERE customer_id IS NOT NULL),2) pct_aumento_sobre_identificados""")

# ---------------------------------------------------------------- E
if 'E' in SECS:
    # evento identificado más cercano (antes y después) para cada tx App/Web, población completa, vía ASOF JOIN.
    # Se evalúa en la hora real y en placebos desplazados ±7d, ±30d; se recorta a tx lejos de los bordes (±31d).
    ev = "(SELECT customer_id, ts FROM de WHERE customer_id IS NOT NULL)"
    rows = []
    for shift in [0, 7*24, -7*24, 30*24, -30*24]:
        sql = f"""
        WITH t AS (SELECT transaction_id, customer_id, fraud, ts + INTERVAL ({shift}) HOUR tsx FROM tx
                   WHERE channel IN ('App','Web') AND ts BETWEEN TIMESTAMP '2023-07-19' AND TIMESTAMP '2026-05-17'),
        prv AS (SELECT t.transaction_id, t.fraud, t.tsx, e.ts prev_ts FROM t ASOF LEFT JOIN {ev} e
                ON t.customer_id = e.customer_id AND t.tsx >= e.ts),
        nxt AS (SELECT t.transaction_id, e.ts next_ts FROM t ASOF LEFT JOIN {ev} e
                ON t.customer_id = e.customer_id AND t.tsx <= e.ts),
        j AS (SELECT p.fraud, date_diff('second', p.prev_ts, p.tsx) dprev, date_diff('second', p.tsx, n.next_ts) dnext
              FROM prv p JOIN nxt n USING (transaction_id))
        SELECT {shift} desplaz_h, fraud, count(*) n,
          count(*) FILTER (WHERE dprev <= 3600 OR dnext <= 3600) hit1h,
          count(*) FILTER (WHERE dprev <= 86400 OR dnext <= 86400) hit24h
        FROM j GROUP BY 1, 2 ORDER BY 2"""
        df = con.execute(sql).df()
        rows.append(df)
        print(f"  desplazamiento {shift}h listo [{time.time()-T0:.0f}s]")
    import pandas as pd
    r = pd.concat(rows)
    r['pct1h'] = (100*r.hit1h/r.n).round(3)
    r['pct24h'] = (100*r.hit24h/r.n).round(3)
    print("\n== E1 tx App/Web con evento identificado del mismo cliente en ±1h/±24h (real=0h, resto placebo)")
    print(r.to_string(index=False))
    # IC95 (Wald) de la diferencia fraude - legítima en ±24h, y razón observado/placebo
    for sh in [0]:
        a = r[(r.desplaz_h == sh)]
        f = a[a.fraud].iloc[0]; l = a[~a.fraud].iloc[0]
        pf, pl = f.hit24h/f.n, l.hit24h/l.n
        se = math.sqrt(pf*(1-pf)/f.n + pl*(1-pl)/l.n)
        print(f"±24h fraude {100*pf:.2f}% ({f.hit24h}/{f.n}) vs legítima {100*pl:.2f}% ({l.hit24h}/{l.n});"
              f" dif IC95 [{100*(pf-pl-1.96*se):.2f}, {100*(pf-pl+1.96*se):.2f}] pp; RR={pf/pl:.2f}")
    tot = r.groupby('desplaz_h')[['n', 'hit1h', 'hit24h']].sum()
    tot['pct1h'] = (100*tot.hit1h/tot.n).round(3); tot['pct24h'] = (100*tot.hit24h/tot.n).round(3)
    print("\n== E2 total por desplazamiento (0 = real)"); print(tot.to_string())
    show("E3 cobertura: clientes con tx App/Web que tienen algún evento identificado", """
    WITH c AS (SELECT DISTINCT customer_id FROM de WHERE customer_id IS NOT NULL)
    SELECT count(DISTINCT t.customer_id) cli_tx_appweb, count(DISTINCT c.customer_id) con_eventos,
           (SELECT count(*) FROM c) cli_con_eventos_total,
           (SELECT count(*) FROM de WHERE customer_id IS NOT NULL)*1.0/(SELECT count(*) FROM c) ev_por_cliente
    FROM (SELECT DISTINCT customer_id FROM tx WHERE channel IN ('App','Web')) t LEFT JOIN c USING (customer_id)""")

# ---------------------------------------------------------------- F
if 'F' in SECS:
    show("F1 eventos del cliente 0-30 días tras cada tx fraude: IP de otro país/ciudad", """
    WITH f AS (SELECT customer_id, ts FROM tx WHERE fraud)
    SELECT count(*) n_pares_evento_post_fraude, count(DISTINCT d.customer_id) clientes,
      count(*) FILTER (WHERE d.ip_country <> c.country) ip_pais_distinto,
      count(*) FILTER (WHERE d.ip_city <> c.city) ip_ciudad_distinta
    FROM f JOIN de d ON d.customer_id = f.customer_id AND d.ts BETWEEN f.ts AND f.ts + INTERVAL 30 DAY
    JOIN cu c ON c.customer_id = d.customer_id""")
    show("F2 tx fraude fuera del país del cliente: ¿algún evento ±7d con IP en el país de la tx?", """
    WITH f AS (SELECT t.transaction_id, t.customer_id, t.ts, t.country tpais, c.country cpais
               FROM tx t JOIN cu c USING (customer_id) WHERE t.fraud AND t.country <> c.country)
    SELECT count(DISTINCT f.transaction_id) fraudes_fuera_pais,
      count(d.event_id) eventos_7d, count(d.event_id) FILTER (WHERE d.ip_country = f.tpais) ev_ip_en_pais_tx
    FROM f LEFT JOIN de d ON d.customer_id = f.customer_id AND d.ts BETWEEN f.ts - INTERVAL 7 DAY AND f.ts + INTERVAL 7 DAY""")

# ---------------------------------------------------------------- G (extras)
if 'G' in SECS:
    show("G1 IP nula en todo de", """
    SELECT count(*) n, count(*) FILTER (WHERE ip_address IS NULL) ip_nula,
           count(*) FILTER (WHERE ip_address IS NULL AND customer_id IS NOT NULL) ip_nula_ident FROM de""")
    # tasa ±24h en el periodo completo (sin recortar bordes), como en el hallazgo
    show("G2 tx App/Web con evento identificado en ±24h, periodo completo", """
    WITH t AS (SELECT transaction_id, customer_id, fraud, ts FROM tx WHERE channel IN ('App','Web')),
    e AS (SELECT customer_id, ts FROM de WHERE customer_id IS NOT NULL),
    prv AS (SELECT t.transaction_id, t.fraud, t.ts, e.ts pts FROM t ASOF LEFT JOIN e ON t.customer_id = e.customer_id AND t.ts >= e.ts),
    nxt AS (SELECT t.transaction_id, e.ts nts FROM t ASOF LEFT JOIN e ON t.customer_id = e.customer_id AND t.ts <= e.ts),
    j AS (SELECT p.fraud, date_diff('second', p.pts, p.ts) dp, date_diff('second', p.ts, n.nts) dn FROM prv p JOIN nxt n USING (transaction_id))
    SELECT fraud, count(*) n, count(*) FILTER (WHERE dp <= 86400 OR dn <= 86400) hit24,
           round(100.0*count(*) FILTER (WHERE dp <= 86400 OR dn <= 86400)/count(*),3) pct24
    FROM j GROUP BY 1 ORDER BY 1""")
    # esperado por azar: sesiones identificadas por cliente distribuidas al azar en ~1096 días
    con.execute("""CREATE TEMP TABLE sc AS SELECT min(customer_id) cid, count(*) ne, min(ip_country) k,
        count(customer_id) n_id, count(ip_city) n_city FROM de GROUP BY session_id""")
    show("G3 esperado por azar de ±24h (1-(1-2/1096)^sesiones del cliente), ponderado por tx App/Web", """
    WITH c AS (SELECT cid, count(*) ns FROM sc WHERE cid IS NOT NULL GROUP BY 1)
    SELECT round(100*avg(1 - pow(1 - 2.0/1096, coalesce(c.ns, 0))),3) pct_esperado_azar, avg(coalesce(c.ns,0)) ses_por_cli_ponderado
    FROM tx t LEFT JOIN c ON c.cid = t.customer_id WHERE t.channel IN ('App','Web')""")
    # sesiones 100% anónimas con ciudad: ¿son sesiones de cliente que perdieron todos sus customer_id por el 5% de nulos?
    show("G4 sesiones 100% anónimas con alguna ciudad no nula, por país", """
    SELECT k, count(*) ses_anon_con_ciudad, sum(ne) eventos FROM sc WHERE n_id = 0 AND n_city > 0 GROUP BY 1 ORDER BY 1""")
    show("G5 esperado de sesiones de cliente con 100% customer_id nulo (sum 0.05^ne sobre sesiones con cliente)", """
    SELECT k, count(*) ses_con_cliente, round(sum(pow(0.05, ne)),1) esperado_todo_nulo FROM sc WHERE n_id > 0 GROUP BY 1 ORDER BY 1""")
    show("G6 product_id de eventos identificados: ¿pertenece al mismo cliente? (otra vía de enlace tx-sesión)", """
    SELECT count(*) n_ident, count(d.product_id) con_prod, count(p.product_id) prod_existe,
      count(*) FILTER (WHERE p.customer_id = d.customer_id) prod_mismo_cliente
    FROM de d LEFT JOIN pr p ON p.product_id = d.product_id WHERE d.customer_id IS NOT NULL""")

print(f"\nTotal {time.time()-T0:.0f}s")
