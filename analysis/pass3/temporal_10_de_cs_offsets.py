"""H15: desfase de fecha local en de y cs (¿ts también desplazado +6h?), perfil semanal real de de, y enlace sv<->cc por fechas."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
idx = pd.date_range('2023-06-17', '2026-06-17')
for t in ['de', 'cs']:
    out = {}
    for k in [0, 6, 8]:
        d = con.execute(f"SELECT CAST(ts - INTERVAL {k} HOUR AS DATE) d, count(*) n FROM {t} GROUP BY 1").fetchdf(); d['d'] = pd.to_datetime(d.d)
        s = d.set_index('d').n.reindex(idx, fill_value=0)
        if t == 'cs': s = s[s.index >= '2023-07-01']
        prof = s.groupby(s.index.dayofweek).mean(); r = s/s.groupby(s.index.dayofweek).transform('mean')
        out[k] = list((prof/prof.mean()).round(3)) + [round(r.std(), 4), round(prof.min()/prof.max(), 3)]
    print(t, "filas: offset horas; cols: lun..dom, sd_residuo, min/max perfil"); print(pd.DataFrame(out).T.to_string())
# de: residuo por día de semana: ¿el residuo diario depende del dow (distinto multiplicador)? y ¿forma de la distribución?
d = con.execute("SELECT CAST(ts - INTERVAL 6 HOUR AS DATE) d, count(*) n FROM de GROUP BY 1").fetchdf(); d['d'] = pd.to_datetime(d.d)
s = d.set_index('d').n.reindex(idx, fill_value=0)
r = s/s.groupby(s.index.dayofweek).transform('mean')
print("de residuo pctiles", np.percentile(r, [1, 5, 25, 50, 75, 95, 99]).round(3))
print("de: media mensual relativa (tendencia):"); m = s.groupby(s.index.to_period('Q')).mean(); print((m/m.mean()).round(3).to_dict())
print("de autocorr residuo lag1/7:", round(r.autocorr(1), 3), round(r.autocorr(7), 3))
# ¿de por event_type/categoría tiene perfiles distintos?
g = con.execute("SELECT event_category c, dayofweek(CAST(ts - INTERVAL 6 HOUR AS DATE)) dw, count(*) n FROM de GROUP BY ALL").fetchdf().pivot(index='c', columns='dw', values='n')
print((g.div(g.mean(1), axis=0)).round(3).to_string())
g = con.execute("SELECT channel c, dayofweek(CAST(ts - INTERVAL 6 HOUR AS DATE)) dw, count(*) n FROM de GROUP BY ALL").fetchdf().pivot(index='c', columns='dw', values='n')
print((g.div(g.mean(1), axis=0)).round(3).to_string())
# sv vs cc
print(con.execute("""SELECT count(*) n, avg((s.process_date = c.process_date)::INT) same_pd, avg((s.ts > c.ts)::INT) sv_after,
  quantile_cont(date_diff('minute', c.ts, s.ts)/60.0, [0.01,0.5,0.99]) q_hours, corr(date_diff('minute', c.ts, s.ts)/60.0, s.resp_hours) corr_resp,
  avg(abs(date_diff('minute', c.ts, s.ts)/60.0 - s.resp_hours)) mae_resp FROM sv s JOIN cc c USING(interaction_id)""").fetchdf().T)
