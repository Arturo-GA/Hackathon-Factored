"""Verificador escéptico: process_date = DATE(ts - 6h) en tx y DATE(ts - 8h) en cc.
Chequea: (1) regla y frontera, (2) si viene del raw (no parseo), (3) offsets en otras tablas,
(4) hipótesis alternativa UTC/zona horaria (por país), (5) qué fecha 'porta' el patrón semanal,
(6) trivialidad del 25%."""
import duckdb, glob, os
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchall()

print("== (1) Regla exacta: ts in (pd+K h, pd+K h+24h]")
for t, k in [('tx', 6), ('cc', 8)]:
    print(t, q(f"""select count(*) n,
      sum((process_date = cast(ts - interval {k} hour as date))::int) ok_k,
      sum((process_date = cast(ts - interval {k} hour - interval 1 second as date))::int) ok_k_1s,
      min(epoch(ts) - epoch(process_date::timestamp))/3600 min_h,
      max(epoch(ts) - epoch(process_date::timestamp))/3600 max_h
      from {t} where ts is not null and process_date is not null"""))
    print(' excepciones K-1s por hh:mm:ss', q(f"""select strftime(ts,'%H:%M:%S'), date_diff('day', cast(ts as date), process_date), count(*) from {t}
        where process_date <> cast(ts - interval {k} hour - interval 1 second as date) group by all order by 3 desc limit 5"""))

print("== (2) Raw: process_date == fecha del archivo/partición (muestra de 30 archivos)")
files = sorted(glob.glob('data/raw/transactions/year=*/month=*/day=*/*.csv'))
sample = files[::max(1, len(files)//30)][:30]
bad = 0; tot = 0; offs = set()
for f in sample:
    d = os.path.basename(f).split('_')[-1][:8]
    r = con.execute(f"""select count(*), sum((strftime(process_date::date,'%Y%m%d') <> '{d}')::int),
         min(epoch(transaction_date::timestamp) - epoch(process_date::date::timestamp))/3600,
         max(epoch(transaction_date::timestamp) - epoch(process_date::date::timestamp))/3600
         from read_csv('{f}', header=true, all_varchar=true)""").fetchone()
    tot += r[0]; bad += r[1]; offs.add((round(r[2], 2), round(r[3], 2)))
print(' filas', tot, 'con process_date != fecha archivo', bad, 'rangos horas ts-pd', sorted(offs)[:3], '...', sorted(offs)[-3:])

print("== (3) Otras tablas con process_date")
for t in ['cp', 'sv']:
    r = q(f"""select count(*), min(epoch(ts)-epoch(process_date::timestamp))/3600, max(epoch(ts)-epoch(process_date::timestamp))/3600,
      avg(date_diff('day', cast(ts as date), process_date)) from {t} where ts is not null and process_date is not null""")
    print(t, r)
    for k in [0, 6, 8, 10, 12]:
        print('  ', k, q(f"select avg((process_date = cast(ts - interval {k} hour as date))::double) from {t}"))
print('tr vs cc.ts', q("""select count(*), avg((tr.process_date = cc.process_date)::double), avg((tr.process_date = cast(cc.ts - interval 8 hour as date))::double)
   from tr join cc using(interaction_id)"""))
for t in ['de', 'cs']:
    cols = [c[0] for c in q(f'describe {t}')]
    print(t, 'tiene process_date' if 'process_date' in cols else 'SIN process_date')

print("== (4) Hipótesis zona horaria por país (MX UTC-6, CO UTC-5, AR UTC-3): offset óptimo por país")
for t in ['tx', 'cc']:
    ccol = 'country' if t == 'tx' else None
    if t == 'tx':
        print(t, q(f"""select country, count(*),
          avg((process_date = cast(ts - interval 3 hour - interval 1 second as date))::double) h3,
          avg((process_date = cast(ts - interval 5 hour - interval 1 second as date))::double) h5,
          avg((process_date = cast(ts - interval 6 hour - interval 1 second as date))::double) h6
          from tx group by 1 order by 1"""))
    else:
        print(t, q(f"""select cu.country, count(*),
          avg((cc.process_date = cast(cc.ts - interval 3 hour - interval 1 second as date))::double) h3,
          avg((cc.process_date = cast(cc.ts - interval 5 hour - interval 1 second as date))::double) h5,
          avg((cc.process_date = cast(cc.ts - interval 8 hour - interval 1 second as date))::double) h8
          from cc join cu using(customer_id) group by 1 order by 1"""))
print(' tx por status', q("select status, avg((process_date = cast(ts - interval 6 hour - interval 1 second as date))::double), count(*) from tx group by 1 order by 1"))

print("== (5) Patrón semanal cc: ¿qué fecha lo porta? (ratio max/min por día de semana)")
for lbl, expr in [('process_date', 'process_date'), ('DATE(ts)', 'cast(ts as date)'), ('DATE(ts-8h)', "cast(ts - interval 8 hour as date)")]:
    r = q(f"select dayofweek({expr}) dw, count(*) n from cc group by 1 order by 1")
    ns = [x[1] for x in r]
    print(f' {lbl:14s}', ns, 'max/min=%.3f' % (max(ns)/min(ns)))
# volumen por hora de ts dentro del día contable: ¿hay salto en la hora 8 del día siguiente?
r = q("""select dayofweek(process_date) dw, floor((epoch(ts)-epoch(process_date::timestamp))/3600)::int hh, count(*) n
    from cc where dayofweek(process_date) in (0,6) group by 1,2 order by 1,2""")
import collections
d = collections.defaultdict(dict)
for dw, hh, n in r: d[dw][hh] = n
for dw in d: print(' dw', dw, 'horas desde pd 8..31, primeras/últimas:', [d[dw].get(h) for h in (8, 9, 30, 31)])
# ¿cambia el volumen horario al cruzar medianoche de ts (hora 24 desde pd) en domingo? si fuese UTC real no habría salto
print(' tx hora local=ts por canal Branch (¿sucursal abierta 3am?):', q("""select hour(ts) h, count(*) from tx where channel='Branch' group by 1 order by 1""")[:8])

print("== (6) 25% es trivial: fracción de tx con hora(ts) en 0-5 =", q("select avg((hour(ts)<6)::double) from tx"),
      " vs 6/24 =", 6/24)
print(' pd<DATE(ts) =', q("select sum((process_date < cast(ts as date))::int), avg((process_date < cast(ts as date))::double) from tx"))
print(' desalineación tx vs cc por pd: fracción de horas del reloj (06-08h) =', 2/24)

print("== (7) sv.process_date vs cc de la interacción; semana tx/cp")
print(' sv', q("""select count(*), avg((sv.process_date = cc.process_date)::double), avg((sv.process_date = cast(sv.ts - interval 8 hour as date))::double),
   min(epoch(sv.ts)-epoch(cc.ts))/3600, max(epoch(sv.ts)-epoch(cc.ts))/3600 from sv join cc using(interaction_id)"""))
for t in ['tx', 'cp']:
    for lbl, expr in [('process_date', 'process_date'), ('DATE(ts)', 'cast(ts as date)')]:
        ns = [x[1] for x in q(f"select dayofweek({expr}) dw, count(*) n from {t} group by 1 order by 1")]
        print(f' {t} {lbl:12s}', ns, 'max/min=%.3f' % (max(ns)/min(ns)))
print(' tx: ts exactamente 06:00:00 por lado', q("select date_diff('day', process_date, cast(ts as date)), count(*) from tx where strftime(ts,'%H:%M:%S')='06:00:00' group by 1"))

print("== (8) ¿Qué reloj usa pr.last_tx? (discrimina 'ts real + corte contable' vs 'ts desplazado')")
print(q("describe pr")[-4:])
print(q("""with m as (select product_id, max(ts) mts, max(process_date) mpd from tx group by 1)
  select count(*),
   avg((cast(p.last_tx as date) = cast(m.mts as date))::double) eq_date_ts,
   avg((cast(p.last_tx as date) = m.mpd)::double) eq_pd,
   avg((cast(p.last_tx as date) >= m.mpd)::double) ge_pd,
   median(date_diff('day', m.mpd, cast(p.last_tx as date))) med_diff
  from pr p join m using(product_id) where p.last_tx is not null"""))
