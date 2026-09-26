# H21: tx en sucursales cerradas/antes de apertura; atm_count=0 con tx ATM; cc atendidas por agentes antes de contratacion / inactivos; cp->agente
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("select branch_status, branch_type, has_atms, count(*) n, min(opened), max(opened) from br group by 1,2,3 order by 1,2,3"))
print(q("""select b.branch_status, b.has_atms, t.channel, count(*) n, round(avg((cast(t.ts as date) < b.opened)::int),4) before_open
  from tx t join br b using(branch_id) group by 1,2,3 order by 1,2,3"""))
print(q("""select b.branch_type, t.channel, count(*) n, round(count(*)*1.0/sum(count(*)) over (partition by t.channel),3) shr_in_channel from tx t join br b using(branch_id) group by 1,2 order by 2,1"""))
print(q("select branch_type, count(*) n, round(count(*)*1.0/sum(count(*)) over(),3) shr from br group by 1"))
print(q("select agent_status, agent_type, count(*) from ag group by 1,2 order by 1,2"))
print(q("""select a.agent_status, count(*) n, round(avg((cast(c.ts as date) < a.hire_date)::int),4) before_hire from cc c join ag a using(agent_id) group by 1"""))
print(q("""select a.agent_type, c.itype, c.channel, count(*) n from (select * from cc using sample 200000) c join ag a using(agent_id) group by 1,2,3 order by 1,4 desc limit 30"""))
print(q("""select a.specialty, cp.category, count(*) n from cp join ag a on a.agent_id=cp.assigned_agent_id group by 1,2 order by 1,2 limit 40"""))
