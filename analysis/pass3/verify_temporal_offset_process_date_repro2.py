"""Verificación independiente (reintento) de 'temporal_offset_process_date'.

Enfoque distinto al script original (que prueba CAST(ts - k h AS DATE) = process_date para cada k):
  1. Se calcula d = ts - process_date(00:00) en MICROSEGUNDOS exactos (epoch_us) y su histograma horario.
     El acierto de cualquier desfase entero k se deriva del histograma: d en [k h, k+24 h).
  2. Se miden los extremos exactos de d, la resolución de ts y cuántas filas caen justo en los bordes,
     comparado con lo esperado bajo un entero uniforme en {0..86400} s (intervalo cerrado).
  3. Uniformidad de d dentro de la ventana (chi2 sobre 24 bins horarios).
  4. Min/max de d por país de la tx, por país del cliente y por canal/moneda (si el desfase fuese huso horario variaría).
  5. Hora de ts -> día de process_date (anterior / mismo).
  6. sv y tr contra cc por interaction_id; desfase propio de sv.
  7. Perfil semanal por process_date vs ts::DATE (¿cuál es el 'día' con el que el generador sortea eventos?).
  8-9. Rango temporal y el mismo chequeo leyendo directamente los CSV crudos (fecha de partición del archivo).
Ejecutar: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_temporal_offset_process_date_repro2.py
"""
import duckdb
import numpy as np
import pandas as pd
from scipy import stats

pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
H = 3_600_000_000  # 1 hora en microsegundos
D = "(epoch_us(ts) - epoch_us(process_date::TIMESTAMP))"

best = {}
print("=== 1-3. Distribución exacta de d = ts - process_date por tabla")
for t in ['tx', 'cc', 'cp', 'sv']:
    base = q(f"""SELECT count(*) n, count(ts) n_ts, count(process_date) n_pd,
        min({D}) dmin, max({D}) dmax,
        sum((epoch_us(ts) % 1000000 <> 0)::INT) n_subsec,
        sum((process_date <> ts::DATE)::INT) n_shift
        FROM {t}""").iloc[0]
    hist = q(f"""SELECT floor({D} / {H})::BIGINT hb, count(*) n FROM {t}
        WHERE ts IS NOT NULL AND process_date IS NOT NULL GROUP BY 1 ORDER BY 1""")
    hist = hist.set_index('hb').n
    n = hist.sum()
    acc = {k: hist[(hist.index >= k) & (hist.index <= k + 23)].sum() / n for k in range(0, 13)}
    kbest = max(acc, key=acc.get)
    best[t] = kbest
    print(f"\n[{t}] n={int(base.n):,} (ts nulos={int(base.n - base.n_ts)}, pd nulos={int(base.n - base.n_pd)}); "
          f"d_min={base.dmin / H:.6f} h, d_max={base.dmax / H:.6f} h; ts con fracción de segundo={int(base.n_subsec)}")
    print(f"  ts::DATE <> process_date: {int(base.n_shift):,} ({base.n_shift / base.n:.5%})")
    print("  acierto por k (derivado del histograma): " + ", ".join(f"k{k}={v:.5f}" for k, v in acc.items()))
    print(f"  mejor k={kbest}: acierto={acc[kbest]:.7f}, fallos={n - round(acc[kbest] * n)}")
    if t != 'sv':
        k = kbest
        lo, hi = k * H, (k + 24) * H
        edge = q(f"""SELECT sum(({D} = {lo})::INT) at_lo, sum(({D} = {hi})::INT) at_hi,
                sum(({D} < {lo})::INT) below, sum(({D} > {hi})::INT) above,
                sum((process_date <> CAST(ts - INTERVAL {k} HOUR AS DATE))::INT) exc_direct,
                sum((process_date <> CAST(ts - INTERVAL {k} HOUR AS DATE) AND {D} <> {hi})::INT) exc_not_edge
                FROM {t}""").iloc[0]
        print(f"  bordes: d={k}h exacto: {int(edge.at_lo)}, d={k + 24}h exacto: {int(edge.at_hi)} "
              f"(esperado por borde si ts=pd+{k}h+randint(0,86400)s: {n / 86401:.1f}); por debajo={int(edge.below)}, por encima={int(edge.above)}")
        print(f"  excepciones directas CAST(ts-{k}h)<>pd: {int(edge.exc_direct)}; de ellas NO en el borde superior: {int(edge.exc_not_edge)}")
        # uniformidad en 24 bins horarios dentro de [k, k+24)
        w = hist[(hist.index >= k) & (hist.index <= k + 23)].values
        chi = stats.chisquare(w)
        print(f"  uniformidad 24 bins: min={w.min():,} max={w.max():,} max/min={w.max() / w.min():.4f} CV={w.std() / w.mean():.4%} "
              f"chi2={chi.statistic:.1f} p={chi.pvalue:.3f}")

print("\n=== 4a. tx: d por país de la tx (min/max en horas) y acierto k=6")
print(q(f"""SELECT country, count(*) n, round(min({D})/{H},4) dmin_h, round(max({D})/{H},4) dmax_h,
    sum((process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE))::INT) exc6,
    round(avg((process_date = CAST(ts - INTERVAL 6 HOUR AS DATE))::INT),6) acc6,
    round(avg((process_date = CAST(ts - INTERVAL 5 HOUR AS DATE))::INT),4) acc5,
    round(avg((process_date = CAST(ts - INTERVAL 3 HOUR AS DATE))::INT),4) acc3
    FROM tx GROUP BY 1 ORDER BY n DESC""").to_string(index=False))
print("tx: por país del CLIENTE")
print(q(f"""SELECT u.country, count(*) n, round(min({D.replace('ts', 't.ts').replace('process_date', 't.process_date')})/{H},4) dmin_h,
    round(max({D.replace('ts', 't.ts').replace('process_date', 't.process_date')})/{H},4) dmax_h,
    sum((t.process_date <> CAST(t.ts - INTERVAL 6 HOUR AS DATE))::INT) exc6
    FROM tx t JOIN cu u USING(customer_id) GROUP BY 1 ORDER BY n DESC""").to_string(index=False))
print("tx: por canal y moneda (min/max d)")
print(q(f"""SELECT channel, currency, count(*) n, round(min({D})/{H},4) dmin_h, round(max({D})/{H},4) dmax_h,
    sum((process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE))::INT) exc6 FROM tx GROUP BY ALL ORDER BY 1,2""").to_string(index=False))

print("\n=== 4b. cc y cp por país del cliente (k=8)")
for t in ['cc', 'cp']:
    print(t, "\n" + q(f"""SELECT u.country, count(*) n,
        round(min(epoch_us(c.ts) - epoch_us(c.process_date::TIMESTAMP))/{H},4) dmin_h,
        round(max(epoch_us(c.ts) - epoch_us(c.process_date::TIMESTAMP))/{H},4) dmax_h,
        sum((c.process_date <> CAST(c.ts - INTERVAL 8 HOUR AS DATE))::INT) exc8
        FROM {t} c JOIN cu u USING(customer_id) GROUP BY 1 ORDER BY n DESC""").to_string(index=False))

print("\n=== 5. Hora de ts -> process_date (tx: corte 6h; cc/cp: corte 8h)")
for t, k in [('tx', 6), ('cc', 8), ('cp', 8)]:
    r = q(f"""SELECT hour(ts) h, count(*) n, sum((process_date = ts::DATE - 1)::INT) prev, sum((process_date = ts::DATE)::INT) same,
        sum((process_date NOT IN (ts::DATE, ts::DATE - 1))::INT) other FROM {t} GROUP BY 1 ORDER BY 1""")
    early, mid, late = r[r.h < k], r[r.h == k], r[r.h > k]
    print(f"{t}: horas 0-{k - 1}: n={early.n.sum():,} prev_day={early.prev.sum() / early.n.sum():.6f} | "
          f"hora {k}: n={int(mid.n.sum()):,} prev_day={int(mid.prev.sum())} same={int(mid.same.sum())} | "
          f"horas {k + 1}-23: n={late.n.sum():,} same_day={late.same.sum() / late.n.sum():.6f} | otros días={int(r.other.sum())}")
    sh = r.n / r.n.sum()
    print(f"   hora del día de ts: share min={sh.min():.5f} max={sh.max():.5f} (1/24={1 / 24:.5f})")
print("tx: las filas de hora 6 con process_date = día anterior, ¿todas son 06:00:00 exacto?")
print(q("""SELECT (minute(ts)=0 AND epoch_us(ts) % 60000000 = 0) is_0600_exact, count(*) n FROM tx
    WHERE hour(ts)=6 AND process_date = ts::DATE - 1 GROUP BY 1""").to_string(index=False))
print(q("""SELECT count(*) n_0600_exact, sum((process_date = ts::DATE - 1)::INT) prev, sum((process_date = ts::DATE)::INT) same
    FROM tx WHERE hour(ts)=6 AND minute(ts)=0 AND epoch_us(ts) % 60000000 = 0""").to_string(index=False))

print("\n=== 6. sv y tr contra cc")
print(q("""SELECT count(*) n_sv, count(c.interaction_id) n_match,
    sum((s.process_date = c.process_date)::INT) same_pd,
    round(min(epoch_us(s.ts) - epoch_us(c.ts))/3.6e9, 4) min_gap_h, round(max(epoch_us(s.ts) - epoch_us(c.ts))/3.6e9, 4) max_gap_h,
    round(median((epoch_us(s.ts) - epoch_us(c.ts))/3.6e9), 3) med_gap_h,
    sum((s.ts <= c.ts)::INT) sv_not_after,
    round(corr((epoch_us(s.ts) - epoch_us(c.ts))/3.6e9, s.resp_hours), 4) corr_gap_resp,
    round(median(abs((epoch_us(s.ts) - epoch_us(c.ts))/3.6e9 - s.resp_hours)), 4) med_abs_gap_minus_resp
    FROM sv s LEFT JOIN cc c USING(interaction_id)""").T.to_string())
print("sv: process_date vs fecha de cc.ts - 8h (vía cc) y vs sv.ts - k")
print(q("""SELECT round(avg((s.process_date = CAST(c.ts - INTERVAL 8 HOUR AS DATE))::INT),6) sv_pd_eq_cc_rule,
    round(avg((s.process_date = s.ts::DATE)::INT),4) sv_pd_eq_own_tsdate,
    round(avg((s.ts::DATE <> c.ts::DATE)::INT),4) sv_day_differs_from_cc_day
    FROM sv s JOIN cc c USING(interaction_id)""").to_string(index=False))
print(q("""SELECT count(*) n_tr, count(c.interaction_id) n_match, sum((t.process_date = c.process_date)::INT) same_pd
    FROM tr t LEFT JOIN cc c USING(interaction_id)""").to_string(index=False))

print("\n=== 7. Perfil semanal (lun..dom / media) agrupando por process_date vs ts::DATE")
names = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']
for t in ['tx', 'cc', 'cp', 'sv']:
    for lab, col in [('pd ', 'process_date'), ('tsD', 'CAST(ts AS DATE)')]:
        r = q(f"SELECT isodow({col}) dw, count(*) n FROM {t} GROUP BY 1 ORDER BY 1").set_index('dw').n
        rel = r / r.mean()
        we = r.loc[[6, 7]].mean() / r.loc[[1, 2, 3, 4, 5]].mean()
        print(f"  {t} {lab}: " + " ".join(f"{names[i - 1]}={rel[i]:.3f}" for i in range(1, 8)) + f" | finde/entre semana={we:.3f}")

print("\n=== 8. Rango temporal")
for t in ['tx', 'cc', 'cp', 'sv']:
    print(t, q(f"SELECT min(process_date) pd_min, max(process_date) pd_max, min(ts) ts_min, max(ts) ts_max FROM {t}").to_string(index=False, header=False))
print("mejores k:", best)

print("\n=== 9. Chequeo sobre los CSV crudos (sin pasar por la base): fecha del archivo, process_date y ts como texto")
RAW = [('tx', 'transactions', 'transaction_date', 6), ('cc', 'call_center_interactions', 'interaction_date', 8),
       ('cp', 'complaints', 'creation_date', 8), ('sv', 'satisfaction_surveys', 'survey_date', None)]
for t, folder, tscol, k in RAW:
    src = f"read_csv('data/raw/{folder}/*/*/*/*.csv', all_varchar=true, filename=true, header=true)"
    extra = "" if k is None else (f", sum((CAST(strptime(tss, '%Y-%m-%d %H:%M:%S') - INTERVAL {k} HOUR AS DATE)"
                                  f" <> pds::DATE)::INT) exc_k")
    r = con.execute(rf"""WITH s AS (
        SELECT {tscol} tss, process_date pds,
               strptime(regexp_extract(filename, '_(\d{{8}})\.csv$', 1), '%Y%m%d')::DATE fdate
        FROM {src})
      SELECT count(*) n,
        sum((NOT regexp_full_match(tss, '\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}}'))::INT) ts_fmt_raro,
        sum((pds::DATE <> fdate)::INT) pd_ne_archivo,
        min(epoch(strptime(tss, '%Y-%m-%d %H:%M:%S')) - epoch(pds::DATE::TIMESTAMP))/3600 dmin_h,
        max(epoch(strptime(tss, '%Y-%m-%d %H:%M:%S')) - epoch(pds::DATE::TIMESTAMP))/3600 dmax_h
        {extra}
      FROM s""").fetchdf()
    print(t, r.to_string(index=False))
