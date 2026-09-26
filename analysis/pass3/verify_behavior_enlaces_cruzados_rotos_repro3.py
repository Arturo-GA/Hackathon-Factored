"""Verificación independiente (intento 3) de behavior_enlaces_cruzados_rotos. Parte 1:
(A) tx -> pr: dueño y moneda (población completa).
(B) cc.mentioned_products: formato, existencia en pr (product_id y product_number), pertenencia al que llama,
    esperado por azar, y si los IDs inexistentes aparecen en otras tablas.
(C) de.product_id: población completa; existencia, pertenencia; esperado por azar si el producto fuera uniforme."""
import sys, time
import duckdb
import pandas as pd
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()
t0 = time.time()
def P(title, df):
    print(f"\n--- {title} [{time.time()-t0:.0f}s]"); print(df.to_string(index=False)); sys.stdout.flush()

# ---------------- (A)
P("A: tx -> pr (dueño y moneda)", Q("""
  SELECT count(*) n_tx, count(p.product_id) tx_con_prod_en_pr,
         sum((t.customer_id = p.customer_id)::INT) mismo_duenio,
         sum((t.currency = p.currency)::INT) misma_moneda,
         sum((t.customer_id IS NULL)::INT) tx_sin_cliente
  FROM tx t LEFT JOIN pr p ON p.product_id = t.product_id"""))

# ---------------- (B)
con.execute("CREATE TEMP TABLE own AS SELECT product_id, customer_id oc, ptype, pstatus FROM pr")
con.execute("""CREATE TEMP TABLE men AS
  SELECT interaction_id, customer_id caller, raw_tok, upper(trim(raw_tok)) pid FROM (
    SELECT interaction_id, customer_id, unnest(string_split(mentioned_products, ',')) raw_tok
    FROM cc WHERE mentioned_products IS NOT NULL)""")
P("B0: volumen", Q("""SELECT (SELECT count(*) FROM cc) n_cc,
     (SELECT count(mentioned_products) FROM cc) cc_con_menciones,
     count(*) n_menciones, sum((pid='')::INT) vacias, count(DISTINCT pid) pid_distintos,
     round(avg(regexp_full_match(pid, 'PRD-[A-Z0-9]{12}')::INT),4) frac_formato_PRD,
     sum((raw_tok <> pid)::INT) tokens_con_espacios_o_minusc
   FROM men"""))
P("B1: existencia y pertenencia (nivel mención)", Q("""
  SELECT count(*) n_menciones, count(o.product_id) existe_en_pr,
         round(100.0*count(o.product_id)/count(*),3) pct_existe,
         sum((o.oc = m.caller)::INT) del_que_llama,
         sum((o.oc <> m.caller)::INT) de_otro_cliente
  FROM men m LEFT JOIN own o ON o.product_id = m.pid"""))
P("B2: ¿coinciden con pr.product_number?", Q("""
  SELECT count(*) n, sum((pid IN (SELECT upper(product_number) FROM pr))::INT) coincide_product_number FROM men"""))
P("B3: nivel llamada: ¿alguna mención es del cliente? y ¿el que llama tiene productos?", Q("""
  WITH x AS (SELECT m.interaction_id, m.caller, bool_or(coalesce(o.oc = m.caller, false)) any_own,
                    bool_or(o.product_id IS NOT NULL) any_exist
             FROM men m LEFT JOIN own o ON o.product_id = m.pid GROUP BY 1,2),
       np AS (SELECT oc, count(*) k FROM own GROUP BY 1)
  SELECT count(*) llamadas, sum(any_exist::INT) con_alguna_existente, sum(any_own::INT) con_alguna_propia,
         round(avg((np.k IS NOT NULL)::INT),4) frac_llamante_con_productos, round(avg(coalesce(np.k,0)),3) prod_medios_llamante
  FROM x LEFT JOIN np ON np.oc = x.caller"""))
P("B4: esperado por azar de 'propias' entre las existentes (si el producto se eligiera uniforme en pr)", Q("""
  WITH np AS (SELECT oc, count(*) k FROM own GROUP BY 1)
  SELECT count(*) menciones_existentes, sum((o.oc=m.caller)::INT) propias_obs,
         round(sum(coalesce(np.k,0))/(SELECT count(*) FROM own),3) propias_esperadas_azar,
         round(avg((cu1.country = cu2.country)::INT),4) mismo_pais_duenio_vs_llamante
  FROM men m JOIN own o ON o.product_id = m.pid
  LEFT JOIN np ON np.oc = m.caller
  LEFT JOIN cu cu1 ON cu1.customer_id = m.caller LEFT JOIN cu cu2 ON cu2.customer_id = o.oc"""))
P("B5: base de mismo país entre dos clientes al azar", Q("""
  SELECT round(sum(n*n)/(sum(n)*sum(n)),4) p_mismo_pais_azar FROM (SELECT country, count(*)::DOUBLE n FROM cu GROUP BY 1)"""))
P("B6: IDs mencionados (distintos) presentes en otras tablas", Q("""
  WITH d AS (SELECT DISTINCT pid FROM men),
       ptx AS (SELECT DISTINCT product_id FROM tx),
       pde AS (SELECT DISTINCT product_id FROM de WHERE product_id IS NOT NULL),
       pcp AS (SELECT DISTINCT affected_product_id product_id FROM cp WHERE affected_product_id IS NOT NULL)
  SELECT count(*) pid_distintos,
         sum((pid IN (SELECT product_id FROM own))::INT) en_pr,
         sum((pid IN (SELECT product_id FROM ptx))::INT) en_tx,
         sum((pid IN (SELECT product_id FROM pde))::INT) en_de,
         sum((pid IN (SELECT product_id FROM pcp))::INT) en_cp_affected
  FROM d"""))
P("B7: menciones repetidas: ¿el mismo pid inexistente aparece con varios clientes?", Q("""
  SELECT count(*) pid_distintos, sum((nc>1)::INT) pid_con_mas_de_1_cliente, max(nm) max_menciones_por_pid
  FROM (SELECT pid, count(DISTINCT caller) nc, count(*) nm FROM men GROUP BY 1)"""))

# ---------------- (C)
P("C0: volumen de", Q("""SELECT count(*) n_de, count(product_id) de_con_pid, count(customer_id) de_con_cliente,
   sum((product_id IS NOT NULL AND customer_id IS NOT NULL)::INT) con_pid_y_cliente FROM de"""))
P("C1: de.product_id -> pr (población completa, eventos con pid y cliente)", Q("""
  WITH np AS (SELECT oc, count(*) k FROM own GROUP BY 1)
  SELECT count(*) n_eventos, count(o.product_id) existe_en_pr,
         sum((o.oc = d.customer_id)::INT) del_cliente_del_evento,
         round(sum(coalesce(np.k,0))/(SELECT count(*) FROM own),2) propios_esperados_azar_uniforme,
         count(DISTINCT d.product_id) pid_distintos, count(DISTINCT d.customer_id) clientes_distintos
  FROM de d LEFT JOIN own o ON o.product_id = d.product_id LEFT JOIN np ON np.oc = d.customer_id
  WHERE d.product_id IS NOT NULL AND d.customer_id IS NOT NULL"""))
P("C2: de.product_id existencia también en eventos sin cliente", Q("""
  SELECT count(*) n_eventos_pid_sin_cliente, count(o.product_id) existe_en_pr
  FROM de d LEFT JOIN own o ON o.product_id = d.product_id
  WHERE d.product_id IS NOT NULL AND d.customer_id IS NULL"""))
P("C3: ¿el dueño del producto tiene al menos un evento digital propio? (el dueño es un cliente 'digital')", Q("""
  WITH dc AS (SELECT DISTINCT customer_id FROM de WHERE customer_id IS NOT NULL),
       dp AS (SELECT DISTINCT product_id FROM de WHERE product_id IS NOT NULL AND customer_id IS NOT NULL)
  SELECT count(*) pid_distintos, round(avg((o.oc IN (SELECT customer_id FROM dc))::INT),4) duenio_con_eventos,
         round((SELECT count(*) FROM dc)/(SELECT count(*) FROM cu),4) base_frac_clientes_con_eventos
  FROM dp JOIN own o USING (product_id)"""))
print(f"\nFIN parte 1 [{time.time()-t0:.0f}s]")
