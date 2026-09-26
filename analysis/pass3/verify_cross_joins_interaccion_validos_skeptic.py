# Verificador escéptico: cross_joins_interaccion_validos
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("describe ag"))
print(q("select column_name, column_type from (describe cc)"))
# 1. sv
print('== sv')
print(q("""select count(*) n, count(sv.interaction_id) nn, count(distinct sv.interaction_id) nd,
 sum((cc.interaction_id is not null)::int) ex, avg((cc.customer_id=sv.customer_id)::int) same_cust,
 avg((cc.agent_id=sv.agent_id)::int) same_agent, avg((sv.ts>=cc.ts)::int) aft,
 median(date_diff('minute', cc.ts, sv.ts))/60.0 med_h, min(date_diff('minute', cc.ts, sv.ts)) min_m, max(date_diff('hour', cc.ts, sv.ts)) max_h
 from sv left join cc using(interaction_id)"""))
# cc.sent vs sv existence
print(q("""select cc.sent, (sv.interaction_id is not null) in_sv, count(*) n from cc left join (select distinct interaction_id from sv) sv using(interaction_id) group by 1,2 order by 1,2"""))
# 2. tr
print('== tr')
print(q("""select count(*) n, count(distinct tr.interaction_id) nd, sum((cc.interaction_id is not null)::int) ex,
 avg((cc.customer_id=tr.customer_id)::int) same_cust, avg((cc.agent_id=tr.agent_id)::int) same_agent,
 avg((abs(cc.dur-tr.dur)<1)::int) dur_eq, avg((cc.dur=tr.dur)::int) dur_exact from tr left join cc using(interaction_id)"""))
print(q("""select cc.has_transcript, cc.has_recording, (t.interaction_id is not null) in_tr, count(*) n from cc left join (select distinct interaction_id from tr) t using(interaction_id) group by 1,2,3 order by 1,2,3"""))
# 3. cp origin
print('== cp')
print(q("select count(*) n, count(origin_interaction_id) nn from cp"))
# 4. agentes
print('== ag status')
print(q("select agent_status, count(*) n from ag group by 1 order by 2 desc"))
print(q("select a.agent_status, count(*) n, count(distinct c.agent_id) nag from cc c left join ag a using(agent_id) group by 1"))
print(q("select a.agent_status, count(*) n, count(distinct cp.assigned_agent_id) nag from cp left join ag a on a.agent_id=cp.assigned_agent_id group by 1 order by 2 desc"))
print(q("select a.agent_status, a.agent_type, count(*) n from ag a group by 1,2 order by 1,2"))
# agentes en cc vs cp: son los mismos conjuntos?
print(q("""select (a.agent_id in (select distinct agent_id from cc)) in_cc, (a.agent_id in (select distinct assigned_agent_id from cp where assigned_agent_id is not null)) in_cp, a.agent_status, count(*) n
 from ag a group by 1,2,3 order by 1,2,3"""))
# cc antes de hire_date
print(q("""select avg((cast(c.ts as date) < a.hire_date)::int) before_hire, count(*) n from cc c join ag a using(agent_id)"""))
print(q("""select avg((cast(cp.assigned_at as date) < a.hire_date)::int) before_hire_cp, count(*) n from cp join ag a on a.agent_id=cp.assigned_agent_id where cp.assigned_at is not null"""))
print('== extra')
# asignacion cp uniforme por agente?
print(q("""select a.agent_status, count(*) nag, avg(n) cp_por_agente, stddev(n) sd from ag a join (select assigned_agent_id agent_id, count(*) n from cp where assigned_agent_id is not null group by 1) x using(agent_id) group by 1"""))
print(q("select 110/1200.0 share_no_activos, 4061/43980.0 share_cp_asignados, 4061/67095.0 share_cp_total"))
# cobertura sv por resolved / cat
print(q("""select cc.resolved, count(*) n, avg((sv.interaction_id is not null)::int) p_sv, avg((t.interaction_id is not null)::int) p_tr from cc left join sv using(interaction_id) left join (select interaction_id from tr) t using(interaction_id) group by 1"""))
print(q("""select cc.cat, count(*) n, avg((sv.interaction_id is not null)::int) p_sv, avg(cc.has_transcript::int) p_tr from cc left join sv using(interaction_id) group by 1 order by 1"""))
# hire_date rango
print(q("select min(hire_date), max(hire_date), avg((hire_date>date '2023-06-17')::int) p_hire_en_ventana from ag"))
