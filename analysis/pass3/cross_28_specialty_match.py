# H22: coincidencia especialidad agente <-> categoria (cc y cp) afecta resultados? ; agentes activos; mismo pais/acento
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("select a.agent_status, count(*) n from cp join ag a on a.agent_id=cp.assigned_agent_id group by 1"))
print(q("select specialty, count(*) from ag group by 1"))
m_cc = """case when (c.cat='Transaccional' and a.specialty in ('Fraudes','Cobranza')) or (c.cat='Técnico' and a.specialty='Soporte Técnico')
  or (c.cat='Queja' and a.specialty='Quejas y Reclamos') or (c.cat='Retención' and a.specialty='Retención') or (c.cat='Comercial' and a.specialty in ('Ventas','Inversiones'))
  or (c.cat='Producto' and a.specialty in ('Créditos','Inversiones','Ventas')) then 1 else 0 end"""
print(q(f"""select c.cat, {m_cc} mt, count(*) n, round(avg(c.resolved::int),4) fcr, round(avg(c.escalated::int),4) esc, round(avg(c.dur),1) dur
  from cc c join ag a using(agent_id) group by 1,2 order by 1,2"""))
print(q(f"""select (replace(a.country_of_origin,'Mexico','México')=cu.country)::int same_ctry, (a.native_accent=cu.detected_accent)::int same_acc, count(*) n,
  round(avg(c.resolved::int),4) fcr, round(avg((c.sent='Negative')::int),4) neg, round(avg(c.dur),1) dur, round(avg(c.escalated::int),4) esc
  from cc c join ag a using(agent_id) join cu using(customer_id) group by 1,2 order by 1,2"""))
m_cp = """case when (cp.category='Transactions' and a.specialty in ('Fraudes')) or (cp.category='Technical' and a.specialty='Soporte Técnico')
  or (a.specialty='Quejas y Reclamos') or (cp.category='Fees' and a.specialty='Cobranza') then 1 else 0 end"""
print(q(f"""select {m_cp} mt, count(*) n, round(avg(cp.sla::int),4) sla, round(avg(cp.rdays),2) rdays, round(avg(cp.res_sat),3) sat, round(avg(cp.repeat::int),4) rep
  from cp join ag a on a.agent_id=cp.assigned_agent_id group by 1"""))
print(q("""select a.experience_level, count(*) n, round(avg(cp.sla::int),4) sla, round(avg(cp.rdays),2) rdays, round(avg(cp.res_sat),3) sat from cp join ag a on a.agent_id=cp.assigned_agent_id group by 1"""))
