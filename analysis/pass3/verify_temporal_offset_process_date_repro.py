"""Verificación independiente: process_date vs ts (offset fijo por tabla)."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string(index=False)

# 1. Diferencia en segundos ts - process_date (medianoche)
for t in ['tx', 'cc', 'cp', 'sv']:
    print(f"== {t}")
    print(q(f"""WITH d AS (SELECT epoch(ts) - epoch(process_date::TIMESTAMP) s, ts, process_date FROM {t})
      SELECT count(*) n, count(s) n_nn, min(s)/3600 min_h, max(s)/3600 max_h,
        sum((s < 6*3600)::INT) lt6, sum((s >= 6*3600 AND s < 30*3600)::INT) in_6_30,
        sum((s = 30*3600)::INT) eq30, sum((s > 30*3600)::INT) gt30,
        sum((s < 8*3600)::INT) lt8, sum((s >= 8*3600 AND s < 32*3600)::INT) in_8_32,
        sum((s = 32*3600)::INT) eq32, sum((s > 32*3600)::INT) gt32,
        avg((ts::DATE <> process_date)::INT) share_tsdate_ne
      FROM d"""))
    cols = ", ".join(f"round(avg((process_date = CAST(ts - INTERVAL {k} HOUR AS DATE))::INT),5) k{k}" for k in range(0, 10))
    print(q(f"SELECT {cols} FROM {t} WHERE ts IS NOT NULL AND process_date IS NOT NULL"))

# 2. tx excepciones a k=6
print("== tx excepciones k=6")
print(q("""SELECT hour(ts) h, minute(ts) m, second(ts) s, date_diff('day', process_date, ts::DATE) dd, count(*) n
  FROM tx WHERE process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE) GROUP BY ALL ORDER BY n DESC LIMIT 10"""))
print(q("""SELECT count(*) n_ts_0600_exact, sum((process_date = ts::DATE)::INT) same_day, sum((process_date = ts::DATE - 1)::INT) prev_day
  FROM tx WHERE hour(ts)=6 AND minute(ts)=0 AND second(ts)=0 AND microsecond(ts)=0"""))
# 3. Por hora
print(q("""SELECT hour(ts) h, count(*) n, round(avg((process_date = ts::DATE - 1)::INT),5) prevday,
   round(avg((process_date = ts::DATE)::INT),5) sameday FROM tx GROUP BY 1 ORDER BY 1"""))
# 4. Por país
print(q("""SELECT country, count(*) n, round(avg((process_date = CAST(ts - INTERVAL 6 HOUR AS DATE))::INT),6) k6,
   sum((process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE))::INT) exc FROM tx GROUP BY 1 ORDER BY n DESC"""))
# 5. Uniformidad de la 'hora local' (ts-6h) — cuántos en cada hora
print(q("""SELECT min(c) mn, max(c) mx, avg(c) av FROM (SELECT hour(ts - INTERVAL 6 HOUR) h, count(*) c FROM tx GROUP BY 1)"""))
# 6. cc/cp excepciones a k=8 y por hora
for t in ['cc', 'cp']:
    print(t, q(f"""SELECT sum((process_date <> CAST(ts - INTERVAL 8 HOUR AS DATE))::INT) exc8,
        sum((hour(ts)<8 AND process_date = ts::DATE - 1)::INT) early_prev, sum((hour(ts)<8)::INT) early,
        sum((hour(ts)>=8 AND process_date = ts::DATE)::INT) late_same, sum((hour(ts)>=8)::INT) late FROM {t}"""))
print("cc por país (via cliente):")
print(q("""SELECT cu.country, count(*) n, round(avg((cc.process_date = CAST(cc.ts - INTERVAL 8 HOUR AS DATE))::INT),6) k8
  FROM cc JOIN cu USING(customer_id) GROUP BY 1 ORDER BY 1"""))
# 7. sv vs cc
print("== sv vs cc")
print(q("""SELECT count(*) n_sv, count(cc.interaction_id) n_match,
   sum((sv.process_date = cc.process_date)::INT) same_pd,
   sum((sv.process_date = CAST(sv.ts - INTERVAL 8 HOUR AS DATE))::INT) sv_k8,
   sum((sv.process_date = CAST(sv.ts - INTERVAL 6 HOUR AS DATE))::INT) sv_k6,
   sum((sv.process_date = sv.ts::DATE)::INT) sv_k0,
   min(epoch(sv.ts)-epoch(cc.ts))/3600 min_h, max(epoch(sv.ts)-epoch(cc.ts))/3600 max_h,
   quantile_cont((epoch(sv.ts)-epoch(cc.ts))/3600, 0.5) med_h
   FROM sv LEFT JOIN cc USING(interaction_id)"""))
# 8. cc/cp excepciones exactas en el borde
for t in ['cc', 'cp']:
    print(t, q(f"""SELECT hour(ts) h, minute(ts) m, second(ts) s, count(*) n FROM {t}
      WHERE process_date <> CAST(ts - INTERVAL 8 HOUR AS DATE) GROUP BY ALL"""))
    print(t, q(f"""SELECT count(*) n_0800_exact, sum((process_date = ts::DATE)::INT) same_day FROM {t}
      WHERE hour(ts)=8 AND minute(ts)=0 AND second(ts)=0 AND microsecond(ts)=0"""))
# 9. Cambio de día entre tx y cc si se usa ts::DATE vs process_date (ordering 2h)
print(q("""SELECT min(hour(ts)) , max(hour(ts)) FROM tx WHERE microsecond(ts) <> 0"""))
