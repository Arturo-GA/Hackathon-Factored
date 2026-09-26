"""Verificador escéptico (2º intento): temporal_offset_process_date.
Ángulos nuevos respecto de _repro/_skeptic:
 A. CSV crudo, todos los archivos: ¿process_date = fecha de la partición? ¿ts sin zona horaria? (descarta artefacto de parseo)
 B. Frontera: ¿el intervalo es cerrado [K, K+24h] con resolución de 1 s (randint(0, 86400))? -> explica las 'excepciones'
 C. ¿Existe algún reloj 'local' detectable? Perfil horario por canal (Branch/ATM/POS, cc por canal, cp Branch) con ts y con ts-K
 D. Coherencia de 'fecha local' con desfase distinto por tabla: ¿cuántos clientes tienen tx y cc/cp a la vez?
 E. Valor práctico: encontrar 'el cargo del día X' con ventana ±1 día (sin conocer la regla) vs filtro exacto con la fecha equivocada
"""
import time
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string(index=False)
t0 = time.time()
tick = lambda lab: print(f"   [{lab} {time.time()-t0:.0f}s]", flush=True)

print("== A. CSV crudo (todos los archivos): partición vs process_date, formato de ts")
for folder, tcol in [('transactions', 'transaction_date'), ('call_center_interactions', 'interaction_date'),
                     ('complaints', 'creation_date'), ('satisfaction_surveys', 'survey_date')]:
    print(folder, q(f"""SELECT count(*) n, count(DISTINCT filename) files,
        sum((regexp_extract(filename, '_(\\d{{8}})\\.csv$', 1) <> strftime(TRY_CAST(process_date AS DATE), '%Y%m%d'))::INT) pd_ne_particion,
        sum((NOT regexp_full_match({tcol}, '\\d{{4}}-\\d{{2}}-\\d{{2}} \\d{{2}}:\\d{{2}}:\\d{{2}}'))::INT) ts_formato_raro
      FROM read_csv('data/raw/{folder}/year=*/month=*/day=*/*.csv', all_varchar=true, filename=true, header=true,
                    hive_partitioning=false)"""))
    tick(folder)

print("== B. Frontera y resolución: conteo por segundo exacto de desfase s = ts - process_date")
for t, K in [('tx', 6), ('cc', 8), ('cp', 8)]:
    a, b = K * 3600, (K + 24) * 3600
    print(t, q(f"""WITH d AS (SELECT CAST(round(epoch(ts) - epoch(process_date::TIMESTAMP)) AS BIGINT) s, ts, process_date FROM {t})
      SELECT count(*) n, round(count(*)/86401.0, 1) esperado_por_seg,
        sum((s={a})::INT) "s=K", sum((s={a}+1)::INT) "s=K+1s", sum((s={a}+2)::INT) "s=K+2s",
        sum((s={b}-2)::INT) "s=K+24h-2s", sum((s={b}-1)::INT) "s=K+24h-1s", sum((s={b})::INT) "s=K+24h",
        sum((s<{a} OR s>{b})::INT) fuera_rango, sum((microsecond(ts)<>0)::INT) con_fraccion_seg,
        round(avg((ts::DATE <> process_date)::INT), 5) share_cambia_dia
      FROM d"""))
    tick(t)

print("== C. ¿Reloj local detectable? Perfil horario por canal: ts crudo vs ts-K (CV de conteos por hora; Poisson ~1/sqrt(n/24))")
for t, K, chcol in [('tx', 6, 'channel'), ('cc', 8, 'channel'), ('cp', 8, 'rchan')]:
    print(t, q(f"""WITH h AS (SELECT {chcol} ch, hour(ts) h_raw, hour(ts - INTERVAL {K} HOUR) h_sh FROM {t}),
      r AS (SELECT ch, h_raw hh, count(*) c FROM h GROUP BY 1, 2),
      s AS (SELECT ch, h_sh hh, count(*) c FROM h GROUP BY 1, 2)
      SELECT r.ch, sum(r.c) n, round(1/sqrt(sum(r.c)/24.0), 4) cv_poisson,
        round(stddev(r.c)/avg(r.c), 4) cv_ts, round(stddev(s.c)/avg(s.c), 4) cv_ts_menos_K,
        round(sum(CASE WHEN r.hh BETWEEN 0 AND 5 THEN r.c END)/sum(r.c), 4) madrugada_ts,
        round(sum(CASE WHEN s.hh BETWEEN 0 AND 5 THEN s.c END)/sum(s.c), 4) madrugada_ts_menos_K,
        round(sum(CASE WHEN r.hh BETWEEN 9 AND 17 THEN r.c END)/sum(r.c), 4) horario_oficina_ts,
        round(sum(CASE WHEN s.hh BETWEEN 9 AND 17 THEN s.c END)/sum(s.c), 4) horario_oficina_ts_menos_K
      FROM r JOIN s USING (ch, hh) GROUP BY 1 ORDER BY n DESC"""))
    tick(t)

print("== D. Mismos clientes en tablas con desfase distinto (si process_date fuera 'fecha local', tendrían 2 husos)")
print(q("""WITH t AS (SELECT DISTINCT customer_id FROM tx), c AS (SELECT DISTINCT customer_id FROM cc),
             p AS (SELECT DISTINCT customer_id FROM cp)
  SELECT (SELECT count(*) FROM t) cli_tx, (SELECT count(*) FROM t JOIN c USING (customer_id)) cli_tx_y_cc,
         (SELECT count(*) FROM t JOIN p USING (customer_id)) cli_tx_y_cp"""))
tick('D')

print("== E. Valor práctico: cliente dice 'el cargo del día X'. Muestra ~2,5% de clientes (hash).")
con.execute("""CREATE TEMP TABLE s AS SELECT transaction_id, customer_id, process_date pd, CAST(ts AS DATE) td, amount
               FROM tx WHERE hash(customer_id) % 40 = 0""")
print(q("""SELECT count(*) n_tx, count(DISTINCT customer_id) n_cli,
  round(avg((pd = td)::INT), 4) recall_filtro_exacto_con_la_otra_fecha FROM s"""))
# X = fecha que da el cliente. Caso 1: X = td (fecha del reloj de ts). Caso 2: X = pd.
for lab, xcol in [('X = fecha de ts', 'a.td'), ('X = process_date', 'a.pd')]:
    print(lab, q(f"""WITH m AS (
        SELECT a.transaction_id,
          sum((b.pd BETWEEN {xcol} - 1 AND {xcol} + 1)::INT) cand_pd_pm1,
          sum((b.pd BETWEEN {xcol} - 1 AND {xcol} + 1 AND b.amount = a.amount)::INT) cand_pd_pm1_monto,
          sum((b.pd = {xcol} OR b.td = {xcol})::INT) cand_union_exacta,
          sum(((b.pd = {xcol} OR b.td = {xcol}) AND b.amount = a.amount)::INT) cand_union_monto
        FROM s a JOIN s b ON a.customer_id = b.customer_id
         AND b.pd BETWEEN a.pd - 3 AND a.pd + 3
        GROUP BY 1)
      SELECT count(*) n, round(avg(cand_pd_pm1), 4) media_cand_ventana_pm1, round(avg((cand_pd_pm1 = 1)::INT), 4) unico_ventana_pm1,
        round(avg((cand_pd_pm1_monto = 1)::INT), 5) unico_ventana_pm1_con_monto,
        round(avg(cand_union_exacta), 4) media_cand_union, round(avg((cand_union_monto = 1)::INT), 5) unico_union_con_monto
      FROM m"""))
    tick(lab)

print("== F. sv/tr heredan process_date de cc; regla por país en tx (fuera de [6h,30h])")
print(q("""SELECT count(*) n_sv, count(c.interaction_id) con_cc, round(avg((s.process_date = c.process_date)::INT), 6) same_pd,
   round(min(epoch(s.ts) - epoch(c.ts))/3600, 3) min_h, round(max(epoch(s.ts) - epoch(c.ts))/3600, 3) max_h
   FROM sv s LEFT JOIN cc c USING (interaction_id)"""))
print(q("""SELECT count(*) n_tr, round(avg((t.process_date = c.process_date)::INT), 6) same_pd FROM tr t JOIN cc c USING (interaction_id)"""))
print(q("""SELECT country, count(*) n, sum((s < 21600 OR s > 108000)::INT) fuera, sum((s = 108000)::INT) borde_30h
   FROM (SELECT country, epoch(ts) - epoch(process_date::TIMESTAMP) s FROM tx) GROUP BY 1 ORDER BY n DESC"""))
