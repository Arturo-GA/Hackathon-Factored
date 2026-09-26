# ids_28: regla agent_status: solo agentes Active aparecen en cc/sv/tr; reclamos asignados a agentes no activos: ¿peor resolución?
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
for t in ['cc','sv','tr']:
    print(t, q(f"select a.agent_status, count(*) n from {t} join ag a using(agent_id) group by 1"))
print(q("""select coalesce(a.agent_status,'(sin asignar)') st, count(*) n, round(avg(sla::int),4) sla_breach, round(avg(rdays),2) rdays, round(avg(res_sat),3) res_sat,
   round(avg((cp.status in ('Closed','Resolved'))::int),3) closed, round(avg(compensation),2) comp
   from cp left join ag a on a.agent_id=cp.assigned_agent_id group by 1 order by 2 desc"""))
print(q("select status, count(*) from cp group by 1"))
print(q("""select status, count(*) n, sum((assigned_agent_id is null)::int) unassigned, round(avg((assigned_agent_id is null)::int),4) frac_unassigned,
   round(avg((assigned_at is null)::int),4) no_assign_date, round(avg((first_resp_at is null)::int),4) no_first_resp, round(avg((resolved_at is null)::int),4) no_resolved, round(avg((closed_at is null)::int),4) no_closed
   from cp group by 1 order by 2 desc"""))
