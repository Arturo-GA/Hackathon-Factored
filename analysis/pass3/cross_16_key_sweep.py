# H12: barrido de llaves alternativas: existencia y consistencia de cliente entre tablas
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
checks = {
 'sv.interaction_id en cc': "select count(*) n, count(sv.interaction_id) nn, avg((cc.interaction_id is not null)::int) ex, avg((cc.customer_id=sv.customer_id)::int) same_cust, avg((cc.agent_id=sv.agent_id)::int) same_agent, avg((sv.ts>=cc.ts)::int) after from sv left join cc using(interaction_id)",
 'tr.interaction_id en cc': "select count(*) n, avg((cc.interaction_id is not null)::int) ex, avg((cc.customer_id=tr.customer_id)::int) same_cust, avg((cc.agent_id=tr.agent_id)::int) same_agent, avg((cc.has_transcript)::int) flag, avg(abs(cc.dur-tr.dur)<1)::double dur_eq from tr left join cc using(interaction_id)",
 'cc.has_transcript vs tr': "select has_transcript, count(*) n, avg((interaction_id in (select interaction_id from tr))::int) in_tr from cc group by 1",
 'cc.agent_id en ag': "select avg((ag.agent_id is not null)::int) ex from cc left join ag using(agent_id)",
 'cp.assigned_agent_id en ag': "select count(assigned_agent_id) nn, avg((ag.agent_id is not null)::int) filter (where assigned_agent_id is not null) ex from cp left join ag on ag.agent_id=cp.assigned_agent_id",
 'cp.related_branch_id en br': "select count(related_branch_id) nn, avg((br.branch_id is not null)::int) filter (where related_branch_id is not null) ex from cp left join br on br.branch_id=cp.related_branch_id",
 'pr.opening_branch_id en br': "select count(opening_branch_id) nn, avg((br.branch_id is not null)::int) filter (where opening_branch_id is not null) ex, avg((br.country=c.country)::int) filter (where br.branch_id is not null) same_ctry from pr left join br on br.branch_id=pr.opening_branch_id left join cu c on c.customer_id=pr.customer_id",
 'tx.branch_id en br': "select avg((br.branch_id is not null)::int) ex from (select branch_id from tx where branch_id is not null using sample 200000) t left join br using(branch_id)",
 'cs.campaign_id en mc': "select avg((mc.campaign_id is not null)::int) ex from (select campaign_id from cs using sample 200000) s left join mc using(campaign_id)",
 'cs.ts dentro de campana': "select avg((cast(s.ts as date) between mc.start_date and mc.end_date)::int) inwin from (select * from cs using sample 200000) s join mc using(campaign_id)",
 'cs pais campana = pais cliente': "select avg((mc.target_country = c.country)::int) same, count(*) filter (where mc.target_country is not null) n from (select * from cs using sample 200000) s join mc using(campaign_id) join cu c using(customer_id)",
 'de.utm_campaign en mc': "select count(utm_campaign) nn, avg((utm_campaign in (select campaign_id from mc))::int) filter (where utm_campaign is not null) ex_id, avg((utm_campaign in (select campaign_name from mc))::int) filter (where utm_campaign is not null) ex_name from (select utm_campaign from de where utm_campaign is not null using sample 200000)",
 'tx cliente en cu': "select avg((c.customer_id is not null)::int) ex from (select customer_id from tx using sample 200000) t left join cu c using(customer_id)",
 'de cliente en cu': "select avg((c.customer_id is not null)::int) ex from (select customer_id from de where customer_id is not null using sample 200000) t left join cu c using(customer_id)",
}
for k,s in checks.items():
    try: print('==',k); print(q(s))
    except Exception as e: print('ERR', e)
print(q("select utm_campaign, count(*) from de where utm_campaign is not null group by 1 order by 2 desc limit 5"))
print(q("select target_country, count(*) from mc group by 1"))
