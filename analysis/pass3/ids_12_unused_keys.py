# ids_12: llaves maestras nunca referenciadas: 110 agentes sin llamadas, 25 campañas sin envíos, productos sin tx -> ¿regla determinista?
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("create temp table used as select distinct agent_id from cc")
for col in ['agent_status','agent_type','experience_level','specialty','work_shift','country_of_origin']:
    print(q(f"select {col}, count(*) n, sum((agent_id in (select agent_id from used))::int) with_calls, round(avg((agent_id in (select agent_id from used))::int),3) frac from ag group by 1 order by 2 desc"))
print(q("select (a.agent_id in (select agent_id from used)) has_calls, count(*) n, count(cp.complaint_id) complaints from ag a left join cp on cp.assigned_agent_id=a.agent_id group by 1"))
con.execute("create temp table uc as select distinct campaign_id from cs")
print(q("select campaign_status, count(*) n, sum((campaign_id in (select campaign_id from uc))::int) with_sends, min(start_date), max(start_date) from mc group by 1"))
print(q("select campaign_type, count(*) n, sum((campaign_id in (select campaign_id from uc))::int) with_sends from mc group by 1"))
