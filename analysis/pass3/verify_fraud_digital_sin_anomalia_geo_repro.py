"""Verificación independiente: fraud_digital_sin_anomalia_geo.
Reproduce: (A) ip_country/ip_city vs país/ciudad del cliente; (B) sesiones con >1 IP/país/ciudad/cliente;
(C) IPs compartidas; (D) eventos anónimos atribuibles por sesión y variante 'Mexico'; (E) tx App/Web con
eventos digitales del cliente en ±1h/±24h (fraude vs legítima) + placebo con desplazamiento temporal;
(F) eventos con ip_country != país del cliente tras un fraude."""
import duckdb, time
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
T0 = time.time()
def show(title, sql):
    df = con.execute(sql).df()
    print(f"\n== {title}  [{time.time()-T0:.0f}s]")
    print(df.to_string(index=False))
    return df

# ---------------- A. geolocalización IP vs cliente (eventos identificados)
show("A1 eventos identificados vs cu", """
SELECT count(*) n_ident, count(c.customer_id) n_join_cu,
  count(*) FILTER (WHERE d.ip_country IS NULL) ipc_null,
  count(*) FILTER (WHERE d.ip_country = c.country) ipc_eq,
  count(*) FILTER (WHERE d.ip_country <> c.country) ipc_ne,
  count(*) FILTER (WHERE d.ip_city IS NULL) city_null,
  count(*) FILTER (WHERE d.ip_city = c.city) city_eq,
  count(*) FILTER (WHERE d.ip_city <> c.city) city_ne,
  count(*) FILTER (WHERE d.ip_address IS NULL) ip_null
FROM de d LEFT JOIN cu c ON c.customer_id = d.customer_id
WHERE d.customer_id IS NOT NULL""")
show("A2 ip_country por tipo de evento (anónimo/identificado)", """
SELECT (customer_id IS NULL) anon, ip_country, count(*) n, count(ip_city) n_city_nonnull
FROM de GROUP BY ALL ORDER BY 1, 3 DESC""")
# ciudades: ¿cuántas ciudades distintas por país? (para saber si city_eq es trivial)
show("A3 ciudades distintas por país (cu vs de identificados)", """
SELECT 'cu' src, country, count(DISTINCT city) n_city FROM cu GROUP BY ALL
UNION ALL SELECT 'de_ident', ip_country, count(DISTINCT ip_city) FROM de WHERE customer_id IS NOT NULL GROUP BY ALL
ORDER BY 1,2""")

# ---------------- B. sesiones
con.execute("""CREATE TEMP TABLE s AS
SELECT session_id,
  count(*) ne,
  count(*) FILTER (WHERE customer_id IS NULL) n_anon,
  min(customer_id) cmin, max(customer_id) cmax,
  (min(ip_address) <> max(ip_address)) multi_ip,
  count(*) FILTER (WHERE ip_address IS NULL) ip_null,
  (min(ip_country) <> max(ip_country)) multi_ctry,
  (min(ip_city) <> max(ip_city)) multi_city,
  count(*) FILTER (WHERE ip_city IS NULL) city_null,
  count(*) FILTER (WHERE ip_country = 'Mexico') n_mex_sin_tilde,
  count(*) FILTER (WHERE ip_country = 'México') n_mex_tilde,
  min(ts) tmin, max(ts) tmax,
  min(ts) FILTER (WHERE customer_id IS NOT NULL) tmin_id,
  max(ts) FILTER (WHERE customer_id IS NOT NULL) tmax_id
FROM de GROUP BY 1""")
show("B1 sesiones", """
SELECT count(*) n_sess,
  count(*) FILTER (WHERE session_id IS NULL) sess_null,
  count(*) FILTER (WHERE multi_ip) multi_ip,
  count(*) FILTER (WHERE multi_ctry) multi_ctry,
  count(*) FILTER (WHERE multi_city) multi_city,
  count(*) FILTER (WHERE cmin <> cmax) multi_cust,
  count(*) FILTER (WHERE ip_null > 0 AND ip_null < ne) mezcla_ip_nulo,
  count(*) FILTER (WHERE ip_null = ne) ip_todo_nulo,
  count(*) FILTER (WHERE city_null > 0 AND city_null < ne) mezcla_city_nulo,
  count(*) FILTER (WHERE cmin IS NULL) sess_100_anon,
  count(*) FILTER (WHERE cmin IS NOT NULL AND n_anon = 0) sess_100_ident,
  count(*) FILTER (WHERE cmin IS NOT NULL AND n_anon > 0) sess_mixta,
  max(date_diff('second', tmin, tmax)) max_dur_s,
  quantile_cont(date_diff('second', tmin, tmax), 0.99) p99_dur_s
FROM s""")

# ---------------- C. IPs compartidas entre clientes (eventos identificados, IP no nula)
show("C1 IPs (identificados, no nulas)", """
WITH ip AS (SELECT ip_address, min(customer_id) cmin, max(customer_id) cmax, count(DISTINCT session_id) nsess,
                   (min(ip_country) <> max(ip_country)) multi_ctry
            FROM de WHERE customer_id IS NOT NULL AND ip_address IS NOT NULL GROUP BY 1)
SELECT count(*) n_ip, count(*) FILTER (WHERE cmin <> cmax) ip_multi_cliente,
       count(*) FILTER (WHERE multi_ctry) ip_multi_pais,
       count(*) FILTER (WHERE nsess > 1) ip_multi_sesion, max(nsess) max_sess_por_ip
FROM ip""")
show("C2 IPs con >1 cliente: nº de clientes", """
WITH ip AS (SELECT ip_address, count(DISTINCT customer_id) nc FROM de
            WHERE customer_id IS NOT NULL AND ip_address IS NOT NULL GROUP BY 1 HAVING min(customer_id) <> max(customer_id))
SELECT nc, count(*) n_ip FROM ip GROUP BY 1 ORDER BY 1""")
show("C3 IPs en todo de (incluye anónimos)", """
WITH ip AS (SELECT ip_address, count(*) n, count(DISTINCT session_id) nsess,
                   (min(ip_country) <> max(ip_country)) multi_ctry
            FROM de WHERE ip_address IS NOT NULL GROUP BY 1)
SELECT count(*) n_ip_total, count(*) FILTER (WHERE nsess>1) ip_multi_sesion, count(*) FILTER (WHERE multi_ctry) ip_multi_pais FROM ip""")
show("C4 IPs distintas por cliente", """
WITH c AS (SELECT customer_id, count(DISTINCT ip_address) nip, count(DISTINCT session_id) nsess
           FROM de WHERE customer_id IS NOT NULL GROUP BY 1)
SELECT count(*) n_cli, avg(nip) avg_ip, avg(nsess) avg_sess, sum(nip) sum_ip, sum(nsess) sum_sess FROM c""")

# ---------------- D. eventos anónimos: atribución por sesión y variante 'Mexico'
show("D1 eventos anónimos por tipo de sesión", """
SELECT count(*) anon_ev,
  count(*) FILTER (WHERE s.cmin IS NOT NULL AND s.cmin = s.cmax) atribuibles,
  round(100.0*count(*) FILTER (WHERE s.cmin IS NOT NULL AND s.cmin = s.cmax)/count(*),2) pct_atrib,
  count(*) FILTER (WHERE s.cmin IS NOT NULL AND s.cmin <> s.cmax) sesion_multi_cliente,
  count(*) FILTER (WHERE s.cmin IS NULL) en_sesion_100_anon
FROM de d JOIN s USING(session_id) WHERE d.customer_id IS NULL""")
show("D2 variante 'Mexico' vs 'México' por tipo de sesión (eventos)", """
SELECT CASE WHEN s.cmin IS NULL THEN '100_anon' WHEN s.n_anon=0 THEN '100_ident' ELSE 'mixta' END tipo_sesion,
  (d.customer_id IS NULL) ev_anon, d.ip_country, count(*) n
FROM de d JOIN s USING(session_id) WHERE d.ip_country IN ('Mexico','México')
GROUP BY ALL ORDER BY 1,2,3""")
show("D3 sesiones 100% anónimas: distribución de país", """
SELECT ip_country, count(*) n_ev FROM de d JOIN s USING(session_id) WHERE s.cmin IS NULL GROUP BY 1 ORDER BY 2 DESC""")
show("D4 anónimos atribuidos: ip_country/ip_city = cliente atribuido", """
SELECT count(*) n, count(*) FILTER (WHERE d.ip_country = c.country) ctry_eq,
  count(*) FILTER (WHERE d.ip_city = c.city) city_eq, count(*) FILTER (WHERE d.ip_city <> c.city) city_ne
FROM de d JOIN s USING(session_id) JOIN cu c ON c.customer_id = s.cmin
WHERE d.customer_id IS NULL AND s.cmin = s.cmax""")

# ---------------- E. tx App/Web vs eventos digitales del mismo cliente
# intervalo de eventos identificados por (sesión, cliente); exacto para ±24h si la sesión dura <48h
con.execute("""CREATE TEMP TABLE si AS SELECT cmin customer_id, tmin_id, tmax_id FROM s WHERE cmin IS NOT NULL AND cmin = cmax""")
con.execute("""CREATE TEMP TABLE aw AS SELECT transaction_id, customer_id, ts, fraud, channel FROM tx WHERE channel IN ('App','Web')""")
show("E0 tx App/Web y cobertura de clientes con eventos", """
SELECT count(*) n_tx, count(*) FILTER (WHERE fraud) n_fraud,
  count(*) FILTER (WHERE customer_id IN (SELECT customer_id FROM si)) tx_cli_con_eventos
FROM aw""")
def hitrate(shift_hours, label):
    return show(f"E {label} (desplazamiento {shift_hours}h)", f"""
    WITH t AS (SELECT transaction_id, customer_id, fraud, ts + INTERVAL ({shift_hours}) HOUR tsx FROM aw),
    h AS (SELECT t.transaction_id,
            bool_or(t.tsx BETWEEN si.tmin_id - INTERVAL 1 DAY AND si.tmax_id + INTERVAL 1 DAY) h24,
            bool_or(t.tsx BETWEEN si.tmin_id - INTERVAL 1 HOUR AND si.tmax_id + INTERVAL 1 HOUR) h1
          FROM t JOIN si ON si.customer_id = t.customer_id
           AND t.tsx BETWEEN si.tmin_id - INTERVAL 1 DAY AND si.tmax_id + INTERVAL 1 DAY
          GROUP BY 1)
    SELECT t.fraud, count(*) n, count(h.transaction_id) hit24, round(100.0*count(h.transaction_id)/count(*),3) pct24,
           count(*) FILTER (WHERE h.h1) hit1, round(100.0*count(*) FILTER (WHERE h.h1)/count(*),3) pct1
    FROM t LEFT JOIN h USING(transaction_id) GROUP BY 1 ORDER BY 1""")
hitrate(0, "observado")
hitrate(24*7, "placebo +7d")
hitrate(-24*7, "placebo -7d")

# ---------------- F. eventos con ip_country != país del cliente tras un fraude (30 días)
show("F eventos 0-30d tras tx fraude del cliente", """
WITH f AS (SELECT customer_id, ts FROM tx WHERE fraud)
SELECT count(*) n_ev_post, count(*) FILTER (WHERE d.ip_country <> c.country) ip_pais_distinto,
       count(*) FILTER (WHERE d.ip_city <> c.city) ip_ciudad_distinta
FROM f JOIN de d ON d.customer_id = f.customer_id AND d.ts BETWEEN f.ts AND f.ts + INTERVAL 30 DAY
JOIN cu c ON c.customer_id = d.customer_id""")
print(f"\nTotal {time.time()-T0:.0f}s")
