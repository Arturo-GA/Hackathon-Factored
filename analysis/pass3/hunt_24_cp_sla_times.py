"""hunt_24: reglas numericas en reclamos: rdays vs fechas, sla vs rdays/priority/tiempos, tiempos de respuesta por prioridad,
estado vs antiguedad del reclamo, repeat vs historial real del cliente, res_sat vs compensacion/sla/rdays.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_24_cp_sla_times.py
"""
import duckdb
import pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
q = lambda s: con.execute(s).df()
print('(1) rdays vs fechas')
print(q("""SELECT count(*) n,
  avg(CASE WHEN rdays = date_diff('day', ts, resolved_at) THEN 1.0 ELSE 0 END) eq_diff_day,
  avg(CASE WHEN abs(rdays - epoch(resolved_at - ts)/86400.0) < 1 THEN 1.0 ELSE 0 END) within1,
  corr(rdays, epoch(resolved_at - ts)/86400.0) r,
  min(epoch(resolved_at - ts)/86400.0) mn, max(epoch(resolved_at - ts)/86400.0) mx
  FROM cp WHERE rdays IS NOT NULL AND resolved_at IS NOT NULL""").to_string())
print(q("""SELECT CAST(rdays AS INT) rd, count(*) n, avg(epoch(resolved_at - ts)/86400.0) real_days_avg, min(epoch(resolved_at - ts)/86400.0) mn,
  max(epoch(resolved_at - ts)/86400.0) mx, avg(CASE WHEN sla THEN 1.0 ELSE 0 END) sla_rate
  FROM cp WHERE rdays IS NOT NULL GROUP BY 1 ORDER BY 1""").T.round(2).to_string())
print('(2) sla por prioridad y por rdays<=k')
print(q("""SELECT priority, count(*) n, avg(CASE WHEN sla THEN 1.0 ELSE 0 END) sla, avg(rdays) rdays, 
  avg(epoch(first_resp_at - ts)/3600.0) fresp_h, median(epoch(first_resp_at - ts)/3600.0) fresp_h_med,
  avg(epoch(assigned_at - ts)/3600.0) assign_h, avg(epoch(resolved_at - ts)/86400.0) resol_d,
  avg(CASE WHEN status IN ('Resolved','Closed') THEN 1.0 ELSE 0 END) resolved_share
  FROM cp GROUP BY 1 ORDER BY 1""").round(3).to_string())
print(q("""SELECT status, count(*) n, avg(CASE WHEN sla THEN 1.0 ELSE 0 END) sla, avg(epoch(first_resp_at - ts)/3600.0) fresp_h,
  min(epoch(first_resp_at - ts)/3600.0) fresp_min, max(epoch(first_resp_at - ts)/3600.0) fresp_max,
  avg(epoch(assigned_at - ts)/3600.0) assign_h, min(epoch(assigned_at - ts)/3600.0) a_min, max(epoch(assigned_at - ts)/3600.0) a_max,
  avg(epoch(closed_at - resolved_at)/86400.0) close_after_resol_d
  FROM cp GROUP BY 1 ORDER BY 2 DESC""").round(2).to_string())
print('orden de timestamps (ts<=assigned<=first_resp<=resolved<=closed):')
print(q("""SELECT count(*) FILTER (WHERE assigned_at IS NOT NULL) n_as, avg(CASE WHEN assigned_at >= ts THEN 1.0 ELSE 0 END) FILTER (WHERE assigned_at IS NOT NULL) as_after_ts,
  avg(CASE WHEN first_resp_at >= assigned_at THEN 1.0 ELSE 0 END) FILTER (WHERE first_resp_at IS NOT NULL AND assigned_at IS NOT NULL) fr_after_as,
  avg(CASE WHEN resolved_at >= first_resp_at THEN 1.0 ELSE 0 END) FILTER (WHERE resolved_at IS NOT NULL AND first_resp_at IS NOT NULL) res_after_fr,
  avg(CASE WHEN closed_at >= resolved_at THEN 1.0 ELSE 0 END) FILTER (WHERE closed_at IS NOT NULL AND resolved_at IS NOT NULL) cl_after_res
  FROM cp""").round(4).to_string())
print('(3) sla vs combinacion: tiempos reales cortos?')
print(q("""SELECT CASE WHEN epoch(first_resp_at - ts)/3600.0 < 12 THEN '<12h' WHEN epoch(first_resp_at - ts)/3600.0 < 24 THEN '12-24h'
  WHEN epoch(first_resp_at - ts)/3600.0 < 48 THEN '24-48h' WHEN first_resp_at IS NULL THEN 'null' ELSE '>=48h' END fr, count(*) n, avg(CASE WHEN sla THEN 1.0 ELSE 0 END) sla
  FROM cp GROUP BY 1 ORDER BY 1""").round(4).to_string())
print('(4) estado vs antiguedad (anio del reclamo)')
print(q("""SELECT year(ts) yr, count(*) n, avg(CASE WHEN status='Open' THEN 1.0 ELSE 0 END) open, avg(CASE WHEN status='In Process' THEN 1.0 ELSE 0 END) inproc,
  avg(CASE WHEN status IN ('Resolved','Closed') THEN 1.0 ELSE 0 END) done FROM cp GROUP BY 1 ORDER BY 1""").round(4).to_string())
print('(5) repeat vs historial real del cliente (reclamos previos del mismo cliente)')
print(q("""WITH c AS (SELECT customer_id, ts, repeat, category,
   count(*) OVER (PARTITION BY customer_id ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) nprior,
   count(*) OVER (PARTITION BY customer_id, category ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) nprior_cat,
   count(*) OVER (PARTITION BY customer_id) tot FROM cp)
  SELECT least(nprior,3) nprior, count(*) n, avg(CASE WHEN repeat THEN 1.0 ELSE 0 END) repeat_rate,
   avg(CASE WHEN repeat THEN 1.0 ELSE 0 END) FILTER (WHERE nprior_cat>0) rr_same_cat_prior FROM c GROUP BY 1 ORDER BY 1""").round(4).to_string())
print(q("""WITH c AS (SELECT customer_id, repeat, count(*) OVER (PARTITION BY customer_id) tot FROM cp)
  SELECT least(tot,4) tot, count(*) n, avg(CASE WHEN repeat THEN 1.0 ELSE 0 END) repeat_rate FROM c GROUP BY 1 ORDER BY 1""").round(4).to_string())
print('repeat vs contactos previos en call center (30 dias antes):')
print(q("""WITH x AS (SELECT p.complaint_id, p.repeat, count(c.interaction_id) ncc FROM cp p LEFT JOIN cc c ON c.customer_id=p.customer_id
     AND c.ts BETWEEN p.ts - INTERVAL 30 DAY AND p.ts GROUP BY 1,2)
  SELECT least(ncc,3) ncc30, count(*) n, avg(CASE WHEN repeat THEN 1.0 ELSE 0 END) repeat_rate FROM x GROUP BY 1 ORDER BY 1""").round(4).to_string())
print('(6) res_sat vs compensacion / sla / rdays / resolution')
print(q("""SELECT CASE WHEN compensation IS NULL THEN 'sin' ELSE 'con' END comp, sla, count(*) n, avg(res_sat) res_sat, avg(rdays) rdays
  FROM cp WHERE res_sat IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""").round(3).to_string())
print(q("""SELECT CASE WHEN rdays<=5 THEN 'a<=5' WHEN rdays<=10 THEN 'b6-10' WHEN rdays<=20 THEN 'c11-20' ELSE 'd>20' END rd, count(*) n, avg(res_sat) res_sat
  FROM cp WHERE res_sat IS NOT NULL GROUP BY 1 ORDER BY 1""").round(3).to_string())
print('(7) prioridad vs monto reclamado y rchan Regulator')
print(q("""SELECT priority, count(claimed) n, avg(claimed) claimed_avg, median(claimed) med FROM cp GROUP BY 1 ORDER BY 1""").round(1).to_string())
print('(8) compensacion vs claimed y moneda')
print(q("""SELECT count(*) n, corr(compensation, claimed) r, avg(compensation) comp_avg, min(compensation) mn, max(compensation) mx,
  avg(CASE WHEN compensation > claimed THEN 1.0 ELSE 0 END) comp_gt_claimed FROM cp WHERE compensation IS NOT NULL AND claimed IS NOT NULL""").round(3).to_string())
print(q("""SELECT case_type, count(*) n, count(compensation) ncomp, avg(CASE WHEN compensation IS NOT NULL THEN 1.0 ELSE 0 END) FILTER (WHERE status IN ('Resolved','Closed')) comp_rate_done
  FROM cp GROUP BY 1""").round(3).to_string())
