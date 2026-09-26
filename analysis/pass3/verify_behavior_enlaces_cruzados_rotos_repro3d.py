"""Verificación independiente (intento 3) de behavior_enlaces_cruzados_rotos. Parte 4 (alcance del título):
(F1) nulo empírico de 'propios' en de.product_id con 30 emparejamientos placebo (sin NULLs) vs 16 observados.
(F2) tr.mentioned_entities.products (tipo de producto): ¿el cliente tiene un producto de ese tipo? real vs placebo.
(F3) de.event_value vs montos de tx del MISMO cliente (muestra 2% de clientes por hash): exacto al centavo real vs placebo."""
import sys, time
import duckdb
import numpy as np
import pandas as pd
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()
t0 = time.time()


def P(title, df):
    print(f"\n--- {title} [{time.time()-t0:.0f}s]")
    print(df.to_string(index=False))
    sys.stdout.flush()


con.execute("CREATE TEMP TABLE own AS SELECT product_id, customer_id oc, ptype FROM pr")
con.execute("""CREATE TEMP TABLE dx AS SELECT d.event_id, d.customer_id ec, o.oc
               FROM de d JOIN own o USING (product_id) WHERE d.product_id IS NOT NULL AND d.customer_id IS NOT NULL""")
vals = []
for j in range(30):
    r = Q(f"""SELECT sum((oc = pc)::INT) FROM (SELECT oc, coalesce(lead(ec) OVER w, first_value(ec) OVER w) pc FROM dx
              WINDOW w AS (ORDER BY hash(event_id || '{j}')))""").iloc[0, 0]
    vals.append(int(r))
vals = np.array(vals)
real = int(Q("SELECT sum((oc = ec)::INT) FROM dx").iloc[0, 0])
print(f"\nF1: propios observados={real}; placebo (30 emparejamientos) media={vals.mean():.2f} sd={vals.std(ddof=1):.2f} "
      f"min={vals.min()} max={vals.max()} ; placebos>={real}: {(vals >= real).sum()}/30")
sys.stdout.flush()

# F2: tipo de producto mencionado en transcript vs productos del cliente
con.execute("""CREATE TEMP TABLE tt AS SELECT transcript_id, customer_id, json_extract_string(mentioned_entities, '$.products') ptype_m
               FROM tr WHERE json_extract_string(mentioned_entities, '$.products') IS NOT NULL""")
con.execute("""CREATE TEMP TABLE ttp AS SELECT *, coalesce(lead(customer_id) OVER w, first_value(customer_id) OVER w) plac
               FROM tt WINDOW w AS (ORDER BY hash(transcript_id || 'z'))""")
con.execute("CREATE TEMP TABLE cpt AS SELECT DISTINCT customer_id, ptype FROM pr")
rows = []
for lab, col in [('real', 'customer_id'), ('placebo', 'plac')]:
    rows.append(Q(f"""SELECT '{lab}' emparejamiento, count(*) n, round(avg((c.customer_id IS NOT NULL)::INT),4) cliente_tiene_ese_tipo
                      FROM ttp t LEFT JOIN cpt c ON c.customer_id = t.{col} AND c.ptype = t.ptype_m"""))
P("F2: tr.products (tipo) presente en la cartera del cliente", pd.concat(rows))

# F3: de.event_value vs tx del mismo cliente (muestra 2% clientes)
con.execute("CREATE TEMP TABLE sc AS SELECT customer_id FROM cu WHERE hash(customer_id || 'f3') % 50 = 0")
con.execute("""CREATE TEMP TABLE ev AS SELECT d.event_id, d.customer_id, d.event_type, d.event_value, CAST(round(d.event_value*100) AS BIGINT) c
               FROM de d JOIN sc USING (customer_id) WHERE d.event_value IS NOT NULL AND d.event_value > 0""")
con.execute("""CREATE TEMP TABLE evp AS SELECT *, coalesce(lead(customer_id) OVER w, first_value(customer_id) OVER w) plac
               FROM ev WINDOW w AS (ORDER BY hash(event_id || 'q'))""")
con.execute("""CREATE TEMP TABLE ts AS SELECT t.customer_id, CAST(round(t.amount*100) AS BIGINT) c, CAST(round(t.amount_usd*100) AS BIGINT) cu
               FROM tx t JOIN sc USING (customer_id)""")
P("F3a: volumen muestra", Q("""SELECT (SELECT count(*) FROM sc) clientes, (SELECT count(*) FROM ev) eventos_con_valor,
    (SELECT count(*) FROM ts) tx, (SELECT round(min(event_value),2) FROM ev) mn, (SELECT round(median(event_value),2) FROM ev) med,
    (SELECT round(max(event_value),2) FROM ev) mx"""))
rows = []
for lab, col in [('real', 'customer_id'), ('placebo', 'plac')]:
    rows.append(Q(f"""SELECT '{lab}' emparejamiento, count(*) n_eventos, sum(m::INT) exacto_amount, sum(mu::INT) exacto_amount_usd FROM (
        SELECT e.event_id, coalesce(bool_or(t.c = e.c), false) m, coalesce(bool_or(t.cu = e.c), false) mu
        FROM evp e LEFT JOIN ts t ON t.customer_id = e.{col} GROUP BY 1)"""))
P("F3b: de.event_value = monto de alguna tx del cliente (real vs placebo)", pd.concat(rows))
print(f"\nFIN parte 4 [{time.time()-t0:.0f}s]")
