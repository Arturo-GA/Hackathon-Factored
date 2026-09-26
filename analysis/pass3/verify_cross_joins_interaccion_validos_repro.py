# Verificacion independiente: cross_joins_interaccion_validos
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()

print("== unicidad de llaves")
print(q("select count(*) n, count(distinct interaction_id) nd, count(interaction_id) nn from cc"))
print(q("select count(*) n, count(distinct interaction_id) nd, count(interaction_id) nn from sv"))
print(q("select count(*) n, count(distinct interaction_id) nd, count(interaction_id) nn from tr"))

print("== sv -> cc")
print(q("""select count(*) n,
  sum((c.interaction_id is not null)::int) found,
  sum((c.customer_id = s.customer_id)::int) same_cust,
  sum((c.agent_id = s.agent_id)::int) same_agent,
  sum((s.agent_id is null)::int) sv_agent_null,
  sum((s.ts >= c.ts)::int) is_after,
  median(epoch(s.ts - c.ts)/3600.0) med_h,
  min(epoch(s.ts - c.ts)/3600.0) min_h, max(epoch(s.ts - c.ts)/3600.0) max_h
  from sv s left join cc c on c.interaction_id = s.interaction_id"""))
# cuantas cc tienen >1 encuesta
print(q("select k, count(*) from (select interaction_id, count(*) k from sv group by 1) group by 1 order by 1"))

print("== tr -> cc")
print(q("""select count(*) n,
  sum((c.interaction_id is not null)::int) found,
  sum((c.customer_id = t.customer_id)::int) same_cust,
  sum((c.agent_id = t.agent_id)::int) same_agent,
  sum((c.dur = t.dur)::int) dur_exact,
  sum((abs(c.dur - t.dur) < 1)::int) dur_lt1,
  corr(c.dur, t.dur) r
  from tr t left join cc c on c.interaction_id = t.interaction_id"""))

print("== has_transcript vs existencia en tr")
print(q("""select c.has_transcript, count(*) n, sum((t.interaction_id is not null)::int) in_tr
  from cc c left join (select distinct interaction_id from tr) t using(interaction_id) group by 1 order by 1"""))

print("== cp.origin_interaction_id")
print(q("select count(*) n, count(origin_interaction_id) nonnull from cp"))

print("== estado de agentes en cc")
print(q("""select a.agent_status, count(*) n, avg((c.ts::date < a.hire_date)::int) before_hire
  from cc c left join ag a using(agent_id) group by 1 order by 2 desc"""))
print(q("select avg((c.ts::date < a.hire_date)::int) before_hire_all, count(*) from cc c join ag a using(agent_id)"))
print("== estado de agentes en cp")
print(q("""select a.agent_status, count(*) n, count(*)*1.0/sum(count(*)) over () pct
  from cp c left join ag a on a.agent_id = c.assigned_agent_id group by 1 order by 2 desc"""))
print(q("select count(*) n, count(assigned_agent_id) nn from cp"))
print("== distribucion de agentes (tabla ag) y agentes distintos usados")
print(q("select agent_status, count(*) from ag group by 1 order by 2 desc"))
print(q("""select a.agent_status, count(distinct c.agent_id) agentes_cc from cc c join ag a using(agent_id) group by 1"""))
print(q("""select a.agent_status, count(distinct c.assigned_agent_id) agentes_cp from cp c join ag a on a.agent_id=c.assigned_agent_id group by 1"""))
# agentes de sv/tr
print(q("select count(*) - count(a.agent_id) sv_agent_not_in_ag from sv s left join ag a using(agent_id)"))
print("== detalle diferencia de duracion tr vs cc")
print(q("""select count(*) n, count(t.dur) tr_dur_nn, count(c.dur) cc_dur_nn,
  sum((t.dur is null or c.dur is null)::int) any_null,
  sum((t.dur is not null and c.dur is not null and t.dur <> c.dur)::int) differ,
  max(abs(t.dur - c.dur)) maxdiff
  from tr t join cc c using(interaction_id)"""))
