"""hunt_38: cp.repeat (= is_repeat_complainer) y cp.sla (= sla_breached): coherencia con el historial y con los tiempos.
(1) clientes con un solo reclamo marcados como reincidentes; (2) consistencia del flag dentro del cliente;
(3) sla_breached vs rdays (dias reales ts->resolved_at) y vs horas a primera respuesta.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_38_repeat_flag.py
"""
import duckdb
import pandas as pd
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='300MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
q = lambda s: con.execute(s).df()
print(q("""WITH c AS (SELECT customer_id, count(*) n, sum(CASE WHEN repeat THEN 1 ELSE 0 END) k FROM cp GROUP BY 1)
  SELECT least(n,4) n_reclamos, count(*) clientes, sum(CASE WHEN k>0 THEN 1 ELSE 0 END) con_flag,
    avg(CASE WHEN k>0 THEN 1.0 ELSE 0 END) share_con_flag,
    avg(CASE WHEN k>0 AND k<n THEN 1.0 ELSE 0 END) share_flag_mixto, avg(CASE WHEN k=n THEN 1.0 ELSE 0 END) share_todos_flag
  FROM c GROUP BY 1 ORDER BY 1""").round(4).to_string())
print('primer reclamo del cliente marcado reincidente:', q("""WITH c AS (SELECT repeat, row_number() OVER (PARTITION BY customer_id ORDER BY ts) rn FROM cp)
  SELECT count(*) n, avg(CASE WHEN repeat THEN 1.0 ELSE 0 END) rate FROM c WHERE rn=1""").to_dict('records'))
print('sla_breached vs dias de resolucion (resueltos):')
print(q("""SELECT CASE WHEN rdays<=3 THEN 'a 1-3' WHEN rdays<=7 THEN 'b 4-7' WHEN rdays<=15 THEN 'c 8-15' WHEN rdays<=22 THEN 'd 16-22' ELSE 'e 23-30' END rd,
  count(*) n, avg(CASE WHEN sla THEN 1.0 ELSE 0 END) breached FROM cp WHERE rdays IS NOT NULL GROUP BY 1 ORDER BY 1""").round(4).to_string())
print('sla_breached por prioridad x (rdays>7):')
print(q("""SELECT priority, rdays>7 largo, count(*) n, avg(CASE WHEN sla THEN 1.0 ELSE 0 END) breached FROM cp WHERE rdays IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""").round(4).to_string())
print('sla_breached en reclamos sin resolver (Open/In Process) vs antiguedad:')
print(q("""SELECT status, CASE WHEN date_diff('day', ts, TIMESTAMP '2026-06-17') > 60 THEN '>60d' ELSE '<=60d' END edad, count(*) n,
  avg(CASE WHEN sla THEN 1.0 ELSE 0 END) breached FROM cp WHERE status IN ('Open','In Process') GROUP BY 1,2 ORDER BY 1,2""").round(4).to_string())
print('distribucion de horas a asignacion y primera respuesta (uniformes?):')
print(q("""SELECT width, count(*) n FROM (SELECT CAST(floor(epoch(first_resp_at - ts)/3600/6) AS INT)*6 width FROM cp WHERE first_resp_at IS NOT NULL) GROUP BY 1 ORDER BY 1""").T.to_string())
print(q("""SELECT width, count(*) n FROM (SELECT CAST(floor(epoch(assigned_at - ts)/3600/2) AS INT)*2 width FROM cp WHERE assigned_at IS NOT NULL) GROUP BY 1 ORDER BY 1""").T.to_string())
print('closed_at - resolved_at (dias):', q("""SELECT min(epoch(closed_at-resolved_at)/86400) mn, max(epoch(closed_at-resolved_at)/86400) mx, avg(epoch(closed_at-resolved_at)/86400) av FROM cp WHERE closed_at IS NOT NULL AND resolved_at IS NOT NULL""").round(2).to_dict('records'))
print('resuelto antes de la primera respuesta:', q("""SELECT count(*) n, avg(CASE WHEN resolved_at < first_resp_at THEN 1.0 ELSE 0 END) pct FROM cp WHERE resolved_at IS NOT NULL AND first_resp_at IS NOT NULL""").to_dict('records'))
print('reclamos cuya ventana de resolucion excede el fin de datos (resolved_at > 2026-06-17):', q("""SELECT count(*) n FROM cp WHERE resolved_at > TIMESTAMP '2026-06-18'""").to_dict('records'))
print('primera respuesta - asignacion (h): cuantiles', q("""SELECT min(h) mn, quantile_cont(h,[0.1,0.25,0.5,0.75,0.9]) q, max(h) mx FROM (SELECT epoch(first_resp_at - assigned_at)/3600.0 h FROM cp WHERE first_resp_at IS NOT NULL AND assigned_at IS NOT NULL)""").to_dict('records'))
print('asignacion - ts (h): cuantiles', q("""SELECT min(h) mn, quantile_cont(h,[0.1,0.25,0.5,0.75,0.9]) q, max(h) mx FROM (SELECT epoch(assigned_at - ts)/3600.0 h FROM cp WHERE assigned_at IS NOT NULL)""").to_dict('records'))
print('horas primera respuesta por prioridad (media, n):', q("""SELECT priority, avg(epoch(first_resp_at - ts)/3600.0) h, count(first_resp_at) n FROM cp GROUP BY 1 ORDER BY 1""").round(2).to_dict('records'))
