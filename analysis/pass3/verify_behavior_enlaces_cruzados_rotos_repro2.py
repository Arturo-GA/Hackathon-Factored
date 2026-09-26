"""Verificación (parte 2): ¿los enlaces 'ajenos' apuntan a un gemelo de identidad o son azar?
(1) cc.mentioned_products existentes y de.product_id: ¿dueño comparte email/móvil/apellido/país con el cliente? vs placebo.
(2) de: casos 'propios' observados vs esperados por azar (sum n_productos(cliente)/400k). ¿dueño aparece en la misma sesión?
(3) cp.claimed vs tx del cliente convertidas a la moneda del reclamo con fx del día (±1%, ±0.1%; todo el histórico y 90d previos) vs placebo.
(4) moneda del reclamo por país restringida a claimed no nulo."""
import duckdb
import pandas as pd

pd.set_option("display.width", 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()

con.execute("CREATE TEMP TABLE prk AS SELECT product_id, customer_id own_cust FROM pr")
con.execute("""CREATE TEMP TABLE cuk AS SELECT customer_id, lower(trim(email)) em, mobile_phone mob,
               lower(last_name) ln, lower(first_name) fn, country FROM cu""")

print("=== (1a) menciones existentes: dueño vs cliente que llama (real vs placebo) ===")
con.execute("""CREATE TEMP TABLE mx AS
  SELECT m.interaction_id, m.customer_id caller, p.own_cust
  FROM (SELECT interaction_id, customer_id, upper(trim(unnest(string_split(mentioned_products, ',')))) pid
        FROM cc WHERE mentioned_products IS NOT NULL) m JOIN prk p ON p.product_id = m.pid""")
con.execute("""CREATE TEMP TABLE mxp AS SELECT *, lead(caller, 7, caller) OVER (ORDER BY hash(interaction_id, own_cust)) plac FROM mx""")
for lab, col in [('real', 'caller'), ('placebo', 'plac')]:
    print(lab, Q(f"""SELECT count(*) n, sum((a.customer_id=b.customer_id)::INT) mismo_id,
        sum((a.em=b.em)::INT) mismo_email, sum((a.mob=b.mob)::INT) mismo_movil,
        sum((a.ln=b.ln AND a.fn=b.fn)::INT) mismo_nombre, round(avg((a.country=b.country)::INT),4) mismo_pais
        FROM mxp x JOIN cuk a ON a.customer_id=x.{col} JOIN cuk b ON b.customer_id=x.own_cust""").to_string(index=False))

print("\n=== (1b) de.product_id: dueño vs cliente del evento (real vs placebo) ===")
con.execute("""CREATE TEMP TABLE dx AS SELECT d.event_id, d.session_id, d.customer_id ev_cust, p.own_cust
               FROM de d JOIN prk p ON p.product_id = d.product_id
               WHERE d.product_id IS NOT NULL AND d.customer_id IS NOT NULL""")
con.execute("""CREATE TEMP TABLE dxp AS SELECT event_id, session_id, ev_cust, own_cust,
               lead(ev_cust, 7, ev_cust) OVER (ORDER BY hash(event_id)) plac FROM dx""")
for lab, col in [('real', 'ev_cust'), ('placebo', 'plac')]:
    print(lab, Q(f"""SELECT count(*) n, sum((a.customer_id=b.customer_id)::INT) mismo_id,
        sum((a.em=b.em)::INT) mismo_email, sum((a.mob=b.mob)::INT) mismo_movil,
        sum((a.ln=b.ln AND a.fn=b.fn)::INT) mismo_nombre, round(avg((a.country=b.country)::INT),4) mismo_pais
        FROM dxp x JOIN cuk a ON a.customer_id=x.{col} JOIN cuk b ON b.customer_id=x.own_cust""").to_string(index=False))
# esperado por azar si product_id se elige uniforme entre los 400k productos
print(Q("""WITH np AS (SELECT own_cust, count(*) k FROM prk GROUP BY 1)
           SELECT count(*) n_eventos, sum((x.ev_cust = x.own_cust)::INT) propios_obs,
                  round(sum(coalesce(np.k,0))/(SELECT count(*) FROM prk), 2) propios_esperados_azar_uniforme
           FROM dx x LEFT JOIN np ON np.own_cust = x.ev_cust""").to_string(index=False))
# ¿el dueño del producto aparece en la misma sesión? (muestra 2% de sesiones)
con.execute("""CREATE TEMP TABLE ss AS SELECT DISTINCT session_id, customer_id FROM de
               WHERE hash(session_id) % 50 = 0 AND customer_id IS NOT NULL""")
print(Q("""SELECT count(*) eventos_muestra,
           sum((EXISTS (SELECT 1 FROM ss WHERE ss.session_id=x.session_id AND ss.customer_id=x.own_cust))::INT) duenio_en_sesion,
           round(avg((SELECT count(*) FROM ss WHERE ss.session_id=x.session_id)),3) clientes_por_sesion
           FROM dx x WHERE hash(x.session_id) % 50 = 0""").to_string(index=False))

print("\n=== (3) cp.claimed vs tx del cliente convertidas a la moneda del reclamo (fx del día) ===")
con.execute("""CREATE TEMP TABLE cl AS SELECT complaint_id, customer_id, ts, currency, claimed FROM cp
               WHERE claimed IS NOT NULL AND currency IS NOT NULL""")
con.execute("""CREATE TEMP TABLE clp AS SELECT *, lead(customer_id, 1, customer_id) OVER (ORDER BY hash(complaint_id)) plac FROM cl""")
con.execute("""CREATE TEMP TABLE tq AS SELECT customer_id, ts, amount, currency tcur, CAST(ts AS DATE) d FROM tx
               WHERE customer_id IN (SELECT customer_id FROM cl UNION SELECT plac FROM clp)""")
for lab, col in [('real', 'customer_id'), ('placebo', 'plac')]:
    print(lab, Q(f"""SELECT count(*) n, sum(n1::INT) cerca_1pct, sum(n01::INT) cerca_0_1pct,
          sum(n1_90::INT) cerca_1pct_90d_previos, sum(n01_90::INT) cerca_0_1pct_90d_previos FROM (
      SELECT c.complaint_id,
        coalesce(bool_or(abs(v - c.claimed) <= 0.01*c.claimed), false) n1,
        coalesce(bool_or(abs(v - c.claimed) <= 0.001*c.claimed), false) n01,
        coalesce(bool_or(abs(v - c.claimed) <= 0.01*c.claimed AND t_ts < c.ts AND t_ts >= c.ts - INTERVAL 90 DAY), false) n1_90,
        coalesce(bool_or(abs(v - c.claimed) <= 0.001*c.claimed AND t_ts < c.ts AND t_ts >= c.ts - INTERVAL 90 DAY), false) n01_90
      FROM clp c LEFT JOIN (
          SELECT t.customer_id, t.ts t_ts, c2.complaint_id,
                 CASE WHEN t.tcur = c2.currency THEN t.amount ELSE t.amount * f.rate END v
          FROM clp c2 JOIN tq t ON t.customer_id = c2.{col}
          LEFT JOIN fx f ON f.date = t.d AND f.src = t.tcur AND f.dst = c2.currency) j
        ON j.complaint_id = c.complaint_id
      GROUP BY 1)""").to_string(index=False))

print("\n=== (4) moneda del reclamo por país (solo claimed no nulo y moneda no nula) ===")
ct = Q("""SELECT u.country, c.currency, count(*) n FROM cp c JOIN cu u USING (customer_id)
          WHERE c.claimed IS NOT NULL AND c.currency IS NOT NULL GROUP BY 1,2""").pivot(index='country', columns='currency', values='n').fillna(0)
print((ct.div(ct.sum(axis=1), axis=0) * 100).round(1).assign(n=ct.sum(axis=1)).to_string())
