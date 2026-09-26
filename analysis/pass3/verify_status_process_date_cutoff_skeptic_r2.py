"""Verificador escéptico (reintento) de 'status_process_date_cutoff'.
Afirmación: process_date = DATE(ts - 6h) en tx (corte contable 06:00) y DATE(ts - 8h) en cc.
Intentos de refutación / explicación:
 A. ¿Artefacto de parseo o de carga? -> CSV crudos (los 1097 archivos de tx y cc) + comparación fila a fila crudo vs base.
 B. Mecanismo exacto: ¿"corte" o "ts = process_date + K + randint(0..86400 s)"? -> conteo por segundo en los extremos.
 C. ¿Zona horaria / horario de verano? -> desfase mín/máx por mes y filas fuera del intervalo por estado x país.
 D. ¿Cuál fecha es la primaria del generador? -> perfil semanal por hora de ts (¿el escalón del fin de semana
    ocurre a las 00:00 o a las K:00?) y ajuste de convolución en ambos sentidos.
 E. ¿Es "fecha contable"? -> ¿existen process_date de fin de semana? (una fecha contable bancaria no las tendría).
 F. Utilidad: desajuste en búsquedas por fecha exacta y en ventanas "últimos N días".
 G. ¿Se puede validar "cruzar tx con llamadas/reclamos por ts"? -> correlación cruzada horaria tx<->cc y tx<->cp.
Ejecutar: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_status_process_date_cutoff_skeptic_r2.py
"""
import time
import traceback
import duckdb
import numpy as np
import pandas as pd

pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
T0 = time.time()


def section(name):
    def deco(fn):
        print(f"\n===== {name}", flush=True)
        try:
            fn()
        except Exception:
            traceback.print_exc()
        print(f"   [{time.time() - T0:.0f}s]", flush=True)
        return fn
    return deco


K = {'tx': 6, 'cc': 8, 'cp': 8}
S = "(epoch(ts) - epoch(process_date::TIMESTAMP))::BIGINT"   # desfase en segundos


@section("A. CSV crudos: process_date = fecha del archivo; ts sin zona; desfase en el crudo; crudo vs base")
def _a():
    for t, folder, tcol, idcol in [('tx', 'transactions', 'transaction_date', 'transaction_id'),
                                   ('cc', 'call_center_interactions', 'interaction_date', 'interaction_id')]:
        k = K[t]
        src = (f"read_csv('data/raw/{folder}/year=*/month=*/day=*/*.csv', all_varchar=true, filename=true, "
               f"header=true, hive_partitioning=false)")
        r = q(rf"""WITH s AS (SELECT {tcol} tss, process_date pds, regexp_extract(filename, '_(\d{{8}})\.csv$', 1) fd,
                     epoch(TRY_STRPTIME({tcol}, '%Y-%m-%d %H:%M:%S'))::BIGINT - epoch(TRY_CAST(process_date AS DATE)::TIMESTAMP)::BIGINT s
                   FROM {src})
            SELECT count(*) n, count(DISTINCT fd) archivos,
              sum((fd <> strftime(TRY_CAST(pds AS DATE), '%Y%m%d'))::INT) pd_distinto_archivo,
              sum((NOT regexp_full_match(tss, '\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}}'))::INT) ts_formato_raro,
              min(s)/3600.0 smin_h, max(s)/3600.0 smax_h,
              sum((s < {k}*3600 OR s > ({k}+24)*3600)::INT) fuera_intervalo_cerrado
            FROM s""")
        print(t, 'crudo:', r.to_dict('records')[0], flush=True)
        # crudo vs base, fila a fila, en 24 archivos repartidos
        con.execute(f"""CREATE OR REPLACE TEMP TABLE rawsamp AS
            SELECT {idcol} id, {tcol} tss, process_date pds FROM {src}
            WHERE regexp_extract(filename, '_(\\d{{8}})\\.csv$', 1) IN (
               SELECT strftime(d, '%Y%m%d') FROM (SELECT DISTINCT process_date d FROM {t}) USING SAMPLE 24 ROWS)""")
        r = q(f"""SELECT count(*) n_crudo, count(b.{idcol}) en_base,
              sum((strftime(b.ts, '%Y-%m-%d %H:%M:%S') = r.tss)::INT) ts_igual,
              sum((strftime(b.process_date, '%Y-%m-%d') = r.pds)::INT) pd_igual
            FROM rawsamp r LEFT JOIN {t} b ON b.{idcol} = r.id""")
        print(t, 'crudo vs base (24 días al azar):', r.to_dict('records')[0], flush=True)


@section("B. Mecanismo: conteo por SEGUNDO del desfase s = ts - process_date (extremos vs interior)")
def _b():
    for t in ['tx', 'cc', 'cp']:
        k = K[t]
        lo, hi = k * 3600, (k + 24) * 3600
        con.execute(f"CREATE OR REPLACE TEMP TABLE persec AS SELECT {S} s, count(*) c FROM {t} GROUP BY 1")
        r = q(f"""SELECT (SELECT sum(c) FROM persec) n, (SELECT sum(c) FROM persec)/86401.0 esperado_por_seg,
              (SELECT count(*) FROM persec WHERE s BETWEEN {lo} AND {hi}) segundos_distintos,
              (SELECT sum(c) FROM persec WHERE s < {lo} OR s > {hi}) fuera,
              (SELECT c FROM persec WHERE s={lo}) c_lo, (SELECT c FROM persec WHERE s={lo}+1) c_lo1,
              (SELECT c FROM persec WHERE s={hi}-1) c_hi1, (SELECT c FROM persec WHERE s={hi}) c_hi,
              (SELECT avg(c) FROM persec WHERE s > {lo} AND s < {hi}) media_interior,
              (SELECT var_samp(c)/avg(c) FROM persec WHERE s > {lo} AND s < {hi}) var_sobre_media""")
        print(t, f'K={k}h:', {kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in r.to_dict('records')[0].items()})
        # ¿Las 'excepciones' a DATE(ts-Kh) son exactamente el extremo superior?
        r = q(f"""SELECT sum((process_date <> CAST(ts - INTERVAL {k} HOUR AS DATE))::INT) exc_regla,
              sum((process_date <> CAST(ts - INTERVAL {k} HOUR AS DATE) AND {S} = {hi})::INT) exc_en_extremo_sup,
              sum((strftime(ts, '%H:%M:%S') = '{k:02d}:00:00')::INT) n_en_la_marca,
              sum((strftime(ts, '%H:%M:%S') = '{k:02d}:00:00' AND process_date = ts::DATE)::INT) marca_mismo_dia,
              sum((strftime(ts, '%H:%M:%S') = '{k:02d}:00:00' AND process_date = ts::DATE - 1)::INT) marca_dia_anterior,
              sum((process_date < ts::DATE)::INT) pd_menor_fecha_ts,
              sum((process_date < ts::DATE AND hour(ts) < {k})::INT) de_ellas_horas_0_{k - 1},
              sum((process_date < ts::DATE AND hour(ts) >= {k})::INT) de_ellas_hora_ge_{k},
              min(ts) ts_min, max(ts) ts_max, min(process_date) pd_min, max(process_date) pd_max,
              count(DISTINCT process_date) dias_pd
            FROM {t}""")
        print(t, r.to_dict('records')[0], flush=True)


@section("C. Estabilidad: desfase mín/máx por mes (¿horario de verano?) y filas fuera del intervalo por estado x país")
def _c():
    r = q(f"""SELECT strftime(process_date, '%Y-%m') ym, count(*) n, min({S})/3600.0 smin_h, max({S})/3600.0 smax_h,
              avg((hour(ts) < 6)::INT) share_h0_5 FROM tx GROUP BY 1 ORDER BY 1""")
    print('tx meses:', len(r), '| smin_h únicos:', sorted(r.smin_h.round(4).unique())[:5],
          '| smax_h únicos:', sorted(r.smax_h.round(4).unique())[-5:],
          '| share horas 0-5 min/max:', round(r.share_h0_5.min(), 4), round(r.share_h0_5.max(), 4))
    r = q(f"""SELECT strftime(process_date, '%Y-%m') ym, min({S})/3600.0 smin_h, max({S})/3600.0 smax_h FROM cc GROUP BY 1""")
    print('cc meses:', len(r), '| smin_h mínimo:', round(r.smin_h.min(), 4), '| smax_h máximo:', round(r.smax_h.max(), 4))
    r = q(f"""SELECT status, country, count(*) n, sum(({S} < 21600 OR {S} > 108000)::INT) fuera_6_30,
              round(avg((process_date = CAST(ts - INTERVAL 6 HOUR AS DATE))::INT), 6) regla_6h
            FROM tx GROUP BY ALL ORDER BY n DESC""")
    print('tx estado x país: celdas', len(r), '| filas fuera de [6h,30h] total:', int(r.fuera_6_30.sum()),
          '| regla_6h min/max por celda (n>=1000):', r[r.n >= 1000].regla_6h.min(), r[r.n >= 1000].regla_6h.max())
    r = q(f"""SELECT u.country, count(*) n, sum(({S.replace('ts', 'c.ts').replace('process_date', 'c.process_date')} < 28800
              OR {S.replace('ts', 'c.ts').replace('process_date', 'c.process_date')} > 115200)::INT) fuera_8_32
            FROM cc c JOIN cu u USING (customer_id) GROUP BY 1 ORDER BY n DESC""")
    print('cc por país del cliente:', r.to_dict('records'))
    r = q("""SELECT count(*) n, count(c.interaction_id) con_cc, sum((s.process_date = c.process_date)::INT) mismo_pd,
             min(epoch(s.ts) - epoch(c.ts))/3600.0 gap_min_h, max(epoch(s.ts) - epoch(c.ts))/3600.0 gap_max_h
             FROM sv s LEFT JOIN cc c USING (interaction_id)""")
    print('sv vs cc:', r.to_dict('records')[0])
    r = q("""SELECT count(*) n, count(c.interaction_id) con_cc, sum((t.process_date = c.process_date)::INT) mismo_pd
             FROM tr t LEFT JOIN cc c USING (interaction_id)""")
    print('tr vs cc:', r.to_dict('records')[0])


@section("D. ¿Cuál fecha es la primaria? Perfil semanal por hora de ts: ¿dónde está el escalón del fin de semana?")
def _d():
    names = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']
    for t in ['tx', 'cc', 'cp']:
        k = K[t]
        r = q(f"SELECT isodow(ts) dw, hour(ts) h, count(*) n FROM {t} GROUP BY 1, 2 ORDER BY 1, 2")
        r['b'] = (r.dw - 1) * 24 + r.h
        v = r.set_index('b').n.reindex(range(168)).values.astype(float)
        jump = v / np.roll(v, 1) - 1          # cambio relativo respecto de la hora anterior (circular)
        z = (v - np.roll(v, 1)) / np.sqrt(v + np.roll(v, 1))   # z de Poisson del salto
        top = np.argsort(-np.abs(z))[:4]
        desc = [f"{names[b // 24]} {b % 24:02d}:00 ({jump[b]:+.1%}, z={z[b]:+.0f})" for b in top]
        print(f"{t}: 4 mayores saltos hora a hora en la semana de ts ->", '; '.join(desc))
        # salto en medianoche vs en la hora K para sáb y lun
        for dname, dw in [('sáb', 6), ('lun', 1)]:
            b0, bk = (dw - 1) * 24, (dw - 1) * 24 + k
            print(f"   {t} {dname}: salto a las 00:00 = {jump[b0]:+.1%} (z={z[b0]:+.1f}); salto a las {k:02d}:00 = {jump[bk]:+.1%} (z={z[bk]:+.1f})")
        # E. convolución en ambos sentidos (totales por día de la semana)
        f = k / 24.0
        npd = q(f"SELECT isodow(process_date) dw, count(*) n FROM {t} GROUP BY 1 ORDER BY 1").set_index('dw').n.reindex(range(1, 8)).values.astype(float)
        nts = q(f"SELECT isodow(ts) dw, count(*) n FROM {t} GROUP BY 1 ORDER BY 1").set_index('dw').n.reindex(range(1, 8)).values.astype(float)
        pred_ts = (1 - f) * npd + f * np.roll(npd, 1)       # pd primaria: DATE(ts)=pd con prob 1-f, pd+1 con prob f
        pred_pd = (1 - f) * nts + f * np.roll(nts, -1)      # ts primaria (hora uniforme dentro del día de ts)
        e1 = np.max(np.abs(pred_ts / nts - 1)); e2 = np.max(np.abs(pred_pd / npd - 1))
        print(f"   {t} por process_date: " + ' '.join(f"{names[i]}={npd[i]/npd.mean():.3f}" for i in range(7)))
        print(f"   {t} por DATE(ts):     " + ' '.join(f"{names[i]}={nts[i]/nts.mean():.3f}" for i in range(7)))
        print(f"   {t} ajuste 'pd primaria' (predice DATE(ts) desde pd): error máx {e1:.3%} | "
              f"ajuste 'ts primaria' (predice pd desde DATE(ts)): error máx {e2:.3%}", flush=True)


@section("E. ¿'Fecha contable' bancaria? días de fin de semana con process_date propio")
def _e():
    for t in ['tx', 'cc']:
        r = q(f"""SELECT count(DISTINCT process_date) dias, count(DISTINCT CASE WHEN isodow(process_date) >= 6 THEN process_date END) dias_finde,
                  round(avg((isodow(process_date) >= 6)::INT), 4) share_filas_finde FROM {t}""")
        print(t, r.to_dict('records')[0])


@section("F. Utilidad práctica: fecha exacta y ventanas 'últimos N días' (pd vs DATE(ts))")
def _f():
    for t in ['tx', 'cc', 'cp']:
        r = q(f"SELECT count(*) n, round(avg((process_date <> ts::DATE)::INT), 5) share_fecha_distinta FROM {t}")
        print(t, r.to_dict('records')[0])
    for N in [1, 7, 30, 90]:
        r = q(f"""WITH a AS (SELECT DATE '2024-01-01' + (i * 37) anchor FROM range(0, 25) r(i))
                 SELECT avg(xor_n / nullif(pd_n, 0)) frac_discrepante FROM (
                   SELECT a.anchor, sum(((t.process_date BETWEEN a.anchor - {N - 1} AND a.anchor)
                                         <> (t.ts::DATE BETWEEN a.anchor - {N - 1} AND a.anchor))::INT)::DOUBLE xor_n,
                          sum((t.process_date BETWEEN a.anchor - {N - 1} AND a.anchor)::INT) pd_n
                   FROM a JOIN tx t ON t.process_date BETWEEN a.anchor - {N} AND a.anchor + 1
                   GROUP BY 1)""")
        print(f"tx ventana últimos {N} días: fracción de tx que entra/sale según la fecha usada = {r.iloc[0, 0]:.4f} "
              f"(teórico 2*0.25/N = {0.5 / N:.4f})")


@section("G. ¿Hay acoplamiento horario tx<->cc / tx<->cp que permita validar 'cruzar por ts'? (todos los clientes, ±48h)")
def _g():
    for other in ['cc', 'cp']:
        r = q(f"""SELECT floor((epoch(o.ts) - epoch(t.ts)) / 3600)::INT lag_h, count(*) n
                 FROM {other} o JOIN tx t ON t.customer_id = o.customer_id
                  AND t.ts BETWEEN o.ts - INTERVAL 48 HOUR AND o.ts + INTERVAL 48 HOUR
                 GROUP BY 1 ORDER BY 1""")
        r = r[(r.lag_h >= -48) & (r.lag_h < 48)]
        v = r.n.values.astype(float)
        zs = (v - v.mean()) / np.sqrt(v.mean())
        near = r[(r.lag_h >= -3) & (r.lag_h <= 2)]
        print(f"tx->{other}: pares={int(v.sum()):,}, media por hora={v.mean():.0f}, CV observado={v.std() / v.mean():.4f} "
              f"vs Poisson={1 / np.sqrt(v.mean()):.4f}, |z| máx={np.abs(zs).max():.1f} en lag {int(r.lag_h.values[np.argmax(np.abs(zs))])}h")
        print(f"   lags -3..+2h (n): {dict(zip(near.lag_h, near.n))}")
        # mismo cruce pero por día: diferencia de process_date vs diferencia de DATE(ts) (-2..+2 días)
        r2 = q(f"""SELECT date_diff('day', t.process_date, o.process_date) d_pd, count(*) n
                  FROM {other} o JOIN tx t ON t.customer_id = o.customer_id
                   AND t.process_date BETWEEN o.process_date - 2 AND o.process_date + 2
                  GROUP BY 1 ORDER BY 1""")
        print(f"   pares por diferencia de process_date (días -2..+2): {dict(zip(r2.d_pd, r2.n))}", flush=True)


print(f"\nFIN {time.time() - T0:.0f}s")
