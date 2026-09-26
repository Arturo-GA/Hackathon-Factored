"""Verificación independiente de 'status_process_date_cutoff'.
Afirmación: tx.process_date = DATE(ts - 6h) (corte 06:00) y cc.process_date = DATE(ts - 8h) (corte 08:00).
Enfoque propio: trabajo con delta = ts - process_date (en segundos) en vez de probar DATE(ts - k),
lo que muestra el soporte exacto de la relación y la naturaleza de las 'excepciones' de frontera.
"""
import duckdb

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchall()
DELTA = "(epoch(ts) - epoch(process_date::timestamp))"   # segundos entre medianoche de process_date y ts


def block(t, k):
    lo, hi = k * 3600, (k + 24) * 3600
    print(f"\n==================== {t}  (k = {k} h) ====================")
    n, nts, npd, mn_ts, mx_ts, mn_pd, mx_pd, frac = q(f"""select count(*), count(ts), count(process_date), min(ts), max(ts),
        min(process_date), max(process_date), sum((microsecond(ts) <> 0)::int) from {t}""")[0]
    print(f"n={n:,}  ts no nulo={nts:,}  pd no nulo={npd:,}  ts con fracción de segundo={frac}")
    print(f"rango ts: {mn_ts} -> {mx_ts} | rango process_date: {mn_pd} -> {mx_pd}")

    mn, mx, n_lo, n_hi, n_in = q(f"""select min({DELTA}), max({DELTA}),
        sum(({DELTA} = {lo})::int), sum(({DELTA} = {hi})::int),
        sum(({DELTA} >= {lo} and {DELTA} <= {hi})::int) from {t}""")[0]
    print(f"delta ts-pd: min={mn/3600:.4f} h  max={mx/3600:.4f} h | en [{k}h,{k+24}h] cerrado: {n_in:,}/{n:,}")
    print(f"  delta exactamente {k}h (ts=pd {k:02d}:00:00): {n_lo} | exactamente {k+24}h (ts=pd+1 {k:02d}:00:00): {n_hi}")
    # conteo esperado por segundo si ts = pd + k h + randint(0, 86400) (86401 valores posibles)
    print(f"  esperado por segundo si U{{0..86400}}: {n/86401:.1f}")
    # conteo en los segundos vecinos a la frontera (debería ser ~n/86401 cada uno)
    nb = q(f"""select {DELTA} - {lo} s, count(*) from {t}
               where {DELTA} - {lo} in (0,1,2,3,43200,86397,86398,86399,86400) group by 1 order by 1""")
    print("  conteos por segundo exacto (s desde pd+k h):", nb)

    # regla DATE(ts - k h) y alternativas
    for kk in [k - 1, k, k + 1]:
        ok = q(f"select sum((process_date = cast(ts - interval {kk} hour as date))::int) from {t}")[0][0]
        print(f"  pd = DATE(ts-{kk}h): {ok:,}/{n:,} = {ok/n:.6f}  (excepciones {n-ok:,})")
    exc = q(f"""select strftime(ts,'%H:%M:%S') hms, date_diff('day', process_date, cast(ts as date)) lag, count(*)
                from {t} where process_date <> cast(ts - interval {k} hour as date) group by all order by 3 desc""")
    print("  excepciones a DATE(ts-k) por hh:mm:ss y desfase de días:", exc[:10], "(grupos:", len(exc), ")")
    tie = q(f"""select date_diff('day', process_date, cast(ts as date)) lag, count(*) from {t}
                where hour(ts) = {k} and minute(ts) = 0 and second(ts) = 0 and microsecond(ts) = 0 group by 1 order by 1""")
    print(f"  ts exactamente {k:02d}:00:00 -> reparto por desfase (0 = mismo día, 1 = día anterior):", tie)

    # día anterior vs hora
    prev, prev_h_lt_k, prev_h_ge_k, h_lt_k, h_lt_k_prev = q(f"""select
        sum((process_date < cast(ts as date))::int),
        sum((process_date < cast(ts as date) and hour(ts) < {k})::int),
        sum((process_date < cast(ts as date) and hour(ts) >= {k})::int),
        sum((hour(ts) < {k})::int),
        sum((hour(ts) < {k} and process_date = cast(ts as date) - 1)::int) from {t}""")[0]
    print(f"  pd < DATE(ts): {prev:,} ({prev/n:.4%}); de ellas hora<{k}: {prev_h_lt_k:,} ({prev_h_lt_k/prev:.5%}), hora>={k}: {prev_h_ge_k:,}")
    print(f"  tx con hora<{k}: {h_lt_k:,}; con pd = DATE(ts)-1: {h_lt_k_prev:,} ({h_lt_k_prev/h_lt_k:.6f})  | esperado uniforme {k}/24 = {k/24:.4%}")
    otros = q(f"""select date_diff('day', process_date, cast(ts as date)) lag, count(*) from {t} group by 1 order by 1""")
    print("  distribución DATE(ts) - pd (días):", otros)
    by_h = q(f"""select hour(ts) h, avg((process_date = cast(ts as date) - 1)::double) prev_rate, count(*) n
                 from {t} group by 1 order by 1""")
    print("  tasa día-anterior por hora:", [(h, round(r, 6)) for h, r, _ in by_h])
    return n


n_tx = block('tx', 6)

print("\n-- tx: cumplimiento de DATE(ts-6h) por país / estado / canal / tipo")
for col in ['country', 'status', 'channel', 'ttype']:
    r = q(f"""select {col}, count(*) n, sum((process_date = cast(ts - interval 6 hour as date))::int) ok,
              sum((process_date not between cast(ts as date) - 1 and cast(ts as date))::int) fuera_rango
              from tx group by 1 order by n desc""")
    print(col, [(v, n, round(ok / n, 6), f) for v, n, ok, f in r])

# ts dentro de [pd+6h, pd+30h] por grupo: 100% en todos?
r = q(f"""select count(distinct country) filter (where not ok_all) from
          (select country, bool_and({DELTA} between 21600 and 108000) ok_all from tx group by 1)""")
print("países con alguna tx fuera de [6h,30h]:", r[0][0])

n_cc = block('cc', 8)
print("\n-- cc: cumplimiento de DATE(ts-8h) por canal / categoría")
for col in ['channel', 'cat']:
    r = q(f"""select {col}, count(*) n, sum((process_date = cast(ts - interval 8 hour as date))::int) ok from cc group by 1 order by n desc""")
    print(col, [(v, n, round(ok / n, 6)) for v, n, ok in r])

print("\n-- cp (reclamos) para el comentario de cruce: offset ts - pd")
print(q(f"""select count(*), min({DELTA})/3600, max({DELTA})/3600,
           avg((process_date = cast(ts - interval 8 hour as date))::double),
           avg((process_date = cast(ts - interval 6 hour as date))::double) from cp where ts is not null"""))

print("\n-- Desalineación tx vs cc al unir por process_date: franja horaria del reloj ts con pd distinto")
# Para un mismo instante ts, tx asigna DATE(ts-6h) y cc asigna DATE(ts-8h): difieren sólo si hora(ts) en [6,8)
print("fracción de horas del día con pd distinto:", 2 / 24)

print("\n-- ¿Qué fecha porta la estacionalidad semanal? (cc: fuerte; tx: ver)")
for t, k in [('cc', 8), ('tx', 6)]:
    for lbl, expr in [('process_date', 'process_date'), ('DATE(ts)', 'cast(ts as date)')]:
        ns = [x[1] for x in q(f"select isodow({expr}) dw, count(*) from {t} group by 1 order by 1")]
        print(f"{t} {lbl:12s} lun..dom", ns, "max/min=%.3f" % (max(ns) / min(ns)))
    # Escalón intradía: lunes calendario (ts). Horas < k pertenecen al domingo contable, >= k al lunes contable.
    r = q(f"""select hour(ts) h, count(*) from {t} where isodow(cast(ts as date)) = 1 group by 1 order by 1""")
    d = dict(r)
    pre = sum(d[h] for h in range(0, k)) / k
    post = sum(d[h] for h in range(k, 24)) / (24 - k)
    print(f"{t}: lunes (reloj ts) volumen medio por hora: horas 0-{k-1} = {pre:,.0f} | horas {k}-23 = {post:,.0f} | ratio {post/pre:.3f}")
    r = q(f"""select hour(ts) h, count(*) from {t} where isodow(cast(ts as date)) = 1 and hour(ts) between {k-2} and {k+1} group by 1 order by 1""")
    print(f"   horas alrededor del corte (lunes):", r)
