"""Verificador escéptico: temporal_offset_process_date.
Pregunta clave: la relación ts <-> process_date es real (en el CSV crudo, no artefacto de parseo),
pero ¿cuál de las dos fechas es la 'verdadera' fecha del evento? Se prueba con señales internas del
generador: tipo de cambio usado en amount_usd, fecha de apertura del producto, last_transaction_date,
fechas de cierre del rango, y ts de reclamos vs sus fechas de asignación."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string(index=False)

print("== 1. tx: rango de ts - process_date y excepciones (en segundos)")
print(q("""WITH d AS (SELECT epoch(ts) - epoch(process_date::TIMESTAMP) s, ts, process_date FROM tx)
  SELECT count(*) n, min(s)/3600 min_h, max(s)/3600 max_h, sum((s=6*3600)::INT) eq6h, sum((s=30*3600)::INT) eq30h,
         sum((process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE))::INT) exc_k6,
         sum((process_date <> CAST(ts - INTERVAL 6 HOUR - INTERVAL 1 SECOND AS DATE))::INT) exc_k6_1s,
         sum((ts::DATE <> process_date)::INT) n_shift, avg((ts::DATE <> process_date)::INT) share_shift FROM d"""))
print("uniformidad de (ts - process_date) en bins de 1h entre 6 y 30h (min/max/cv de conteos):")
print(q("""WITH b AS (SELECT floor((epoch(ts) - epoch(process_date::TIMESTAMP))/3600) h, count(*) c FROM tx GROUP BY 1)
  SELECT count(*) nbins, min(h) hmin, max(h) hmax, min(c) cmin, max(c) cmax, round(stddev(c)/avg(c),4) cv FROM b WHERE h<30"""))
print(q("""SELECT min(ts) min_ts, max(ts) max_ts, min(process_date) min_pd, max(process_date) max_pd FROM tx"""))

print("== 2. ¿Qué fecha usa el generador para amount_usd? (solo tx donde ts::DATE <> process_date, no USD)")
con.execute("""CREATE TEMP TABLE s AS SELECT currency, amount, amount_usd, ts, process_date FROM tx
  WHERE amount_usd IS NOT NULL AND currency<>'USD' AND ts::DATE <> process_date USING SAMPLE 150000""")
for lab, dcol in [('process_date', 's.process_date'), ('ts::DATE', 'CAST(s.ts AS DATE)')]:
    print(lab, q(f"""SELECT s.currency, count(*) n, count(f.rate) nfx,
        round(avg((abs(s.amount_usd - s.amount*f.rate) <= 0.011)::INT),4) exact_rate,
        round(median(abs(s.amount_usd/(s.amount*f.rate)-1)),6) med_relerr
        FROM s LEFT JOIN fx f ON f.date={dcol} AND f.src=s.currency AND f.dst='USD' GROUP BY 1 ORDER BY 1"""))
print("variación diaria del fx (para saber si el test discrimina): mediana |rate_d/rate_{d-1}-1|")
print(q("""SELECT src, round(median(abs(rate/lag_rate-1)),5) med_daily_change FROM (
   SELECT src, rate, lag(rate) OVER (PARTITION BY src ORDER BY date) lag_rate FROM fx WHERE dst='USD') GROUP BY 1"""))

print("== 3. Apertura de producto vs fecha de tx: ¿se viola opened con ts::DATE o con process_date?")
print(q("""SELECT count(*) n, sum((t.process_date < p.opened)::INT) pd_before_open, sum((t.ts::DATE < p.opened)::INT) tsd_before_open,
     sum((t.process_date = p.opened - 1 AND t.ts::DATE = p.opened)::INT) edge_pd_prev_ts_same
   FROM tx t JOIN pr p USING(product_id)"""))

print("== 4. last_tx del producto vs max(ts) / max(process_date)")
print(q("""WITH m AS (SELECT product_id, max(ts) mts, max(process_date) mpd FROM tx GROUP BY 1)
  SELECT count(*) n, avg((p.last_tx = m.mts)::INT) eq_maxts, avg((p.last_tx::DATE = m.mpd)::INT) eq_maxpd_date,
         avg((p.last_tx::DATE = m.mts::DATE)::INT) eq_maxts_date, avg((p.last_tx IS NULL)::INT) null_lt
  FROM m JOIN pr p USING(product_id)"""))

print("== 5. cc / cp: rango ts - process_date y excepciones a 8h")
for t in ['cc', 'cp']:
    print(t, q(f"""WITH d AS (SELECT epoch(ts) - epoch(process_date::TIMESTAMP) s, ts, process_date FROM {t})
      SELECT count(*) n, min(s)/3600 min_h, max(s)/3600 max_h,
        sum((process_date <> CAST(ts - INTERVAL 8 HOUR AS DATE))::INT) exc_k8,
        round(avg((ts::DATE <> process_date)::INT),4) share_shift FROM d"""))
print("cp: assigned_at / first_resp_at relativo a ts y a process_date (horas)")
print(q("""SELECT round(min(epoch(assigned_at)-epoch(ts))/3600,2) min_as_ts, round(avg((assigned_at < ts)::INT),4) as_before_ts,
     round(avg((assigned_at::DATE < process_date)::INT),4) as_before_pd FROM cp WHERE assigned_at IS NOT NULL"""))

print("== 6. sv vs cc y tr vs cc")
print(q("""SELECT count(*) n, avg((s.process_date = c.process_date)::INT) same_pd, avg((s.process_date = s.ts::DATE)::INT) sv_pd_eq_tsdate,
   min(epoch(s.ts)-epoch(c.ts))/3600 min_h, max(epoch(s.ts)-epoch(c.ts))/3600 max_h,
   avg((s.process_date = CAST(s.ts - INTERVAL 8 HOUR AS DATE))::INT) sv_k8
   FROM sv s JOIN cc c USING(interaction_id)"""))
print(q("""SELECT count(*) n, avg((t.process_date = c.process_date)::INT) same_pd FROM tr t JOIN cc c USING(interaction_id)"""))

print("== 7. por país del cliente (cc) a k=8 y tx a k=6 por country")
print(q("""SELECT u.country, count(*) n, round(avg((c.process_date = CAST(c.ts - INTERVAL 8 HOUR AS DATE))::INT),6) k8
   FROM cc c JOIN cu u USING(customer_id) GROUP BY 1 ORDER BY n DESC"""))
print(q("""SELECT country, count(*) n, round(avg((process_date = CAST(ts - INTERVAL 6 HOUR AS DATE))::INT),6) k6 FROM tx GROUP BY 1 ORDER BY n DESC"""))

print("== 8. patrón semanal: ¿cambia si se agrupa por process_date vs ts::DATE? (cc)")
for lab, dcol in [('process_date', 'process_date'), ('ts::DATE', 'CAST(ts AS DATE)')]:
    print(lab, q(f"""SELECT dayofweek({dcol}) dw, count(*) n FROM cc GROUP BY 1 ORDER BY 1""").replace('\n', ' | '))

print("== 9. perfil semanal relativo (dom..sáb / media) por process_date vs ts::DATE en tx, cp, sv")
for t in ['tx', 'cp', 'sv']:
    for lab, dcol in [('pd', 'process_date'), ('tsd', 'CAST(ts AS DATE)')]:
        r = con.execute(f"""SELECT dayofweek({dcol}) dw, count(*) n FROM {t} GROUP BY 1 ORDER BY 1""").fetchdf()
        print(t, lab, list((r.n / r.n.mean()).round(3)))
print("== 10. cc excepciones a k=8 (detalle)")
print(q("""SELECT ts, process_date FROM cc WHERE process_date <> CAST(ts - INTERVAL 8 HOUR AS DATE)"""))
