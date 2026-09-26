"""Verificación independiente (intento 3) de behavior_enlaces_cruzados_rotos. Parte 3:
(E1) de.product_id: 16 casos 'propios' vs esperado por azar bajo (a) producto uniforme en pr y (b) permutación que conserva
     la frecuencia empírica de cada producto; placebo desplazando clientes entre eventos; detalle de los casos propios.
(E2) ptype de los productos referenciados en de vs pr (¿muestreo uniforme?).
(E3) tr.mentioned_entities: ¿contiene IDs de producto / montos que sí apunten al cliente? (formato y enlace)."""
import sys, time
import duckdb
import pandas as pd
from scipy import stats
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 120)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()
t0 = time.time()


def P(title, df):
    print(f"\n--- {title} [{time.time()-t0:.0f}s]")
    print(df.to_string(index=False))
    sys.stdout.flush()


con.execute("CREATE TEMP TABLE own AS SELECT product_id, customer_id oc, ptype, pstatus FROM pr")
con.execute("""CREATE TEMP TABLE dx AS SELECT event_id, session_id, ts, event_type, customer_id ec, product_id
               FROM de WHERE product_id IS NOT NULL AND customer_id IS NOT NULL""")
# (b) esperado por permutación: sum_c E_c * sum_{p in c} n_p / N
e = Q("""WITH np AS (SELECT product_id, count(*) n FROM dx GROUP BY 1),
              ec AS (SELECT ec, count(*) e FROM dx GROUP BY 1),
              cs AS (SELECT o.oc, sum(coalesce(np.n,0)) s FROM own o LEFT JOIN np USING (product_id) GROUP BY 1)
         SELECT (SELECT count(*) FROM dx) N, sum(ec.e * coalesce(cs.s,0)) / (SELECT count(*) FROM dx) esperado_permutacion
         FROM ec LEFT JOIN cs ON cs.oc = ec.ec""")
P("E1b: esperado de propios si se permutan los product_id entre eventos", e)
obs = int(Q("SELECT sum((o.oc = d.ec)::INT) FROM dx d JOIN own o USING (product_id)").iloc[0, 0])
lam = float(e.esperado_permutacion.iloc[0])
print(f"observado={obs}  esperado_perm={lam:.2f}  P(X>={obs}|Poisson)={stats.poisson.sf(obs-1, lam):.4f}")
# placebo: clientes desplazados entre eventos (varios desplazamientos)
pl = []
for k in [1, 17, 1001, 50021, 300007]:
    pl.append(Q(f"""SELECT {k} desplazamiento, sum((o.oc = x.pc)::INT) propios_placebo FROM (
        SELECT product_id, lead(ec, {k}) OVER (ORDER BY hash(event_id)) pc FROM dx) x JOIN own o USING (product_id)"""))
P("E1c: placebo (cliente de otro evento)", pd.concat(pl))
P("E1d: detalle de los casos propios", Q("""SELECT d.event_type, o.ptype, o.pstatus, count(*) n FROM dx d JOIN own o USING (product_id)
    WHERE o.oc = d.ec GROUP BY ALL ORDER BY n DESC"""))
P("E1e: ¿propios concentrados en pocos clientes/sesiones?", Q("""SELECT count(*) n, count(DISTINCT d.ec) clientes, count(DISTINCT d.session_id) sesiones
    FROM dx d JOIN own o USING (product_id) WHERE o.oc = d.ec"""))

# E2: ptype en de vs pr
P("E2: ptype de productos referenciados en de vs pr", Q("""
   WITH a AS (SELECT o.ptype, count(*) n FROM dx d JOIN own o USING (product_id) GROUP BY 1),
        b AS (SELECT ptype, count(*) n FROM own GROUP BY 1)
   SELECT b.ptype, round(100.0*a.n/sum(a.n) OVER (),2) pct_de, round(100.0*b.n/sum(b.n) OVER (),2) pct_pr
   FROM b LEFT JOIN a USING (ptype) ORDER BY pct_pr DESC"""))
P("E2b: pstatus de productos referenciados en de vs pr", Q("""
   WITH a AS (SELECT o.pstatus, count(*) n FROM dx d JOIN own o USING (product_id) GROUP BY 1),
        b AS (SELECT pstatus, count(*) n FROM own GROUP BY 1)
   SELECT b.pstatus, round(100.0*a.n/sum(a.n) OVER (),2) pct_de, round(100.0*b.n/sum(b.n) OVER (),2) pct_pr
   FROM b LEFT JOIN a USING (pstatus) ORDER BY pct_pr DESC"""))

# E3: tr.mentioned_entities
P("E3a: muestras de mentioned_entities", Q("SELECT customer_id, mentioned_entities FROM tr WHERE mentioned_entities IS NOT NULL LIMIT 6"))
P("E3b: ¿contiene PRD-/CLI-/TXN- o números de producto?", Q("""SELECT count(*) n, count(mentioned_entities) no_nulo,
    sum(regexp_matches(mentioned_entities, 'PRD-')::INT) con_PRD, sum(regexp_matches(mentioned_entities, 'CLI-')::INT) con_CLI,
    sum(regexp_matches(mentioned_entities, 'TXN|TRX|TX-')::INT) con_tx_id,
    sum(regexp_matches(mentioned_entities, '[0-9]{10,}')::INT) con_digitos10 FROM tr"""))
print(f"\nFIN parte 3 [{time.time()-t0:.0f}s]")
