# H12b: llaves de interaccion y sucursal: consistencia de cliente/agente/tiempo
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
checks = {
 'sv.interaction_id en cc': "select count(*) n, count(sv.interaction_id) nn, avg((cc.interaction_id is not null)::int) ex, avg((cc.customer_id=sv.customer_id)::int) same_cust, avg((cc.agent_id=sv.agent_id)::int) same_agent, avg((sv.ts>=cc.ts)::int) aft, median(date_diff('hour', cc.ts, sv.ts)) med_h from sv left join cc using(interaction_id)",
 'tr.interaction_id en cc': "select count(*) n, avg((cc.interaction_id is not null)::int) ex, avg((cc.customer_id=tr.customer_id)::int) same_cust, avg((cc.agent_id=tr.agent_id)::int) same_agent, avg((abs(cc.dur-tr.dur)<1)::int) dur_eq, corr(cc.dur, tr.dur) r_dur from tr left join cc using(interaction_id)",
 'cs pais campana = pais cliente (normalizado)': "select avg((replace(mc.target_country,'Mexico','México') = c.country)::int) same, count(*) n from (select * from cs using sample 200000) s join mc using(campaign_id) join cu c using(customer_id) where mc.target_country is not null",
 'cs segmento campana = segmento cliente': "select mc.target_segment, count(*) n, avg((mc.target_segment = c.segment)::int) same from (select * from cs using sample 200000) s join mc using(campaign_id) join cu c using(customer_id) group by 1",
 'tx.branch_id = pr.opening_branch_id': "select avg((t.branch_id=p.opening_branch_id)::int) same, count(*) n from (select * from tx where branch_id is not null using sample 200000) t join pr p using(product_id)",
 'tx.branch_id = sucursal habitual': "with b as (select customer_id, branch_id, count(*) n from tx where branch_id is not null and hash(customer_id)%10=0 group by 1,2) select avg(mx*1.0/tot) share_top, avg(nb) n_branches, avg(tot) n_tx from (select customer_id, max(n) mx, sum(n) tot, count(*) nb from b group by 1) where tot>=5",
 'cp.related_branch_id pais = pais cliente': "select avg((br.country=c.country)::int) same, count(*) n from cp join br on br.branch_id=cp.related_branch_id join cu c using(customer_id)",
 'cp.related_branch en tx del cliente': "select avg((exists(select 1 from tx t where t.customer_id=cp.customer_id and t.branch_id=cp.related_branch_id))::int) used, count(*) n from cp where related_branch_id is not null",
 'cp.assigned_agent pais vs cliente': "select avg((ag.country_of_origin=c.country)::int) same, count(*) n from cp join ag on ag.agent_id=cp.assigned_agent_id join cu c using(customer_id)",
 'cc agente pais vs cliente': "select avg((ag.country_of_origin=c.country)::int) same, avg((ag.native_accent=c.detected_accent)::int) same_acc, count(*) n from (select * from cc using sample 200000) x join ag using(agent_id) join cu c using(customer_id)",
}
for k,s in checks.items():
    try: print('==',k); print(q(s))
    except Exception as e: print('ERR', e)
print(q("select country_of_origin, native_accent, count(*) from ag group by 1,2 order by 3 desc limit 10"))
print(q("select country, detected_accent, count(*) from cu group by 1,2 order by 3 desc limit 10"))
