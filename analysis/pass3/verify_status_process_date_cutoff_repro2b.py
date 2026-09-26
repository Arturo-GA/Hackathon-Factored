"""Complemento: (1) fracción de segundo real (epoch_us), (2) escalón del sábado en el reloj ts,
(3) el desfase ya viene en el CSV crudo (no es artefacto de carga), (4) cp en la frontera."""
import duckdb, glob, os

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchall()

for t in ['tx', 'cc']:
    print(t, 'filas con fracción de segundo real:', q(f"select sum((epoch_us(ts) % 1000000 <> 0)::int) from {t}")[0][0])

print("\n-- Escalón intradía en sábado y lunes (reloj ts): volumen medio por hora antes/después del corte")
for t, k in [('tx', 6), ('cc', 8)]:
    for dname, dw in [('sábado', 6), ('lunes', 1)]:
        d = dict(q(f"select hour(ts), count(*) from {t} where isodow(cast(ts as date)) = {dw} group by 1"))
        pre = sum(d[h] for h in range(0, k)) / k
        post = sum(d[h] for h in range(k, 24)) / (24 - k)
        mid = sum(d[h] for h in range(0, 24)) / 24
        # alternativa: escalón a medianoche => pre ≈ post
        print(f"{t} {dname}: h0-{k-1} {pre:,.0f}/h | h{k}-23 {post:,.0f}/h | ratio {post/pre:.3f}")

print("\n-- Crudo: transaction_date - process_date en CSV (muestra de 12 archivos de tx y 12 de cc)")
for sub, tcol in [('transactions', 'transaction_date'), ('call_center_interactions', 'interaction_date')]:
    files = sorted(glob.glob(f'data/raw/{sub}/year=*/month=*/day=*/*.csv'))
    sample = files[::max(1, len(files) // 12)][:12]
    tot = bad = 0; mn = 1e9; mx = -1e9
    for f in sample:
        dfile = os.path.basename(f).split('_')[-1][:8]
        r = con.execute(f"""select count(*), sum((strftime(process_date::date, '%Y%m%d') <> '{dfile}')::int),
              min(epoch({tcol}::timestamp) - epoch(process_date::date::timestamp)),
              max(epoch({tcol}::timestamp) - epoch(process_date::date::timestamp))
              from read_csv('{f}', header=true, all_varchar=true)""").fetchone()
        tot += r[0]; bad += r[1]; mn = min(mn, r[2]); mx = max(mx, r[3])
    print(f"{sub}: {len(sample)} archivos, {tot:,} filas, pd != fecha del archivo: {bad}, ts-pd en [{mn/3600:.3f} h, {mx/3600:.3f} h]")

print("\n-- cp: excepciones a DATE(ts-8h)")
print(q("""select strftime(ts,'%H:%M:%S'), date_diff('day', process_date, cast(ts as date)), count(*) from cp
           where process_date <> cast(ts - interval 8 hour as date) group by all"""))
