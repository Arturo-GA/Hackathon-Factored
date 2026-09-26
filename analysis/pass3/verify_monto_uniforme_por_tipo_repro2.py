import duckdb, numpy as np, pandas as pd
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: con.execute(s).df()
K="(case t.currency when 'ARS' then 350.0 when 'COP' then 4000.0 else 1.0 end)"
LO="(case t.ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Payment' then 50 when 'Adjustment' then 10 when 'Deposit' then 50 else 100 end)"
HI="(case t.ttype when 'Purchase' then 500 when 'Withdrawal' then 500 when 'Payment' then 2000 when 'Adjustment' then 1000 when 'Deposit' then 5000 else 10000 end)"
con.execute(f"""create temp table w as select t.transaction_id, t.customer_id, t.product_id, t.ttype, t.tcat, t.channel, t.status, coalesce(t.code,'NA') code, t.country, t.country_raw,
 coalesce(t.mcat,'NA') mcat, t.merchant_name, t.fraud, t.fscore, hour(t.ts) h, dayofweek(t.ts) dow, year(t.ts) y, month(t.ts) m, t.city,
 cu.segment, ntile(5) over (order by cu.income) inc_q, ntile(5) over (order by cu.credit_score) cs_q, cu.cstatus, cu.gender, cu.occupation,
 p.ptype, p.pstatus, ntile(5) over (order by p.bal/{K}) bal_q, p.dpd>0 moroso,
 (t.amount/{K}-{LO})/({HI}-{LO}) u
 from tx t join cu using(customer_id) join pr p using(product_id)""")
print(q("select count(*) from w").to_string())
tot=float(q("select var_pop(u) from w").iloc[0,0])
out=[]
for v in ['ttype','tcat','channel','status','code','country','country_raw','mcat','fraud',"coalesce(floor(fscore/10)::int,-1)",'h','dow','y','m','segment','inc_q','cs_q','cstatus','gender','occupation','ptype','pstatus','bal_q','moroso','city','merchant_name']:
    g=q(f"select {v} g, count(*) n, avg(u) mu, min(u) mn, max(u) mx from w group by 1")
    g=g[g.n>=1000]
    z=(g.mu-0.5)/(np.sqrt(1/12)/np.sqrt(g.n))
    eta=(g.n*(g.mu-0.5)**2).sum()/g.n.sum()/tot
    out.append((v[:30],len(g),int(g.n.min()),round(g.mu.min(),4),round(g.mu.max(),4),round(np.abs(z).max(),2),'%.2e'%eta, round(g.mn.max(),4), round(g.mx.min(),4)))
print(pd.DataFrame(out,columns=['var','ngroups','minn','mu_min','mu_max','max|z|','eta2','max_min_u','min_max_u']).to_string())
# rechazo/codigo/fraude por quintil de u
print(q("""select ntile(5) over (order by u) qq, count(*) n, avg((status='Declined')::int) decl, avg((code='51')::int) c51, avg(fraud::int)*1000 fraud_pm, avg(fscore) fs
 from w group by all order by 1""") if False else q("""with z as (select *, ntile(5) over (order by u) qq from w) select qq, count(*) n, round(avg((status='Declined')::int)*100,2) decl_pct, round(avg((code='51')::int)*100,2) c51_pct, round(avg(fraud::int)*1000,3) fraud_pm, round(avg(fscore),2) fs from z group by 1 order by 1""").to_string())
# efecto cliente/producto: sum n_i (mean_i-0.5)^2 / (1/12) / n_clientes ~ 1 bajo iid
for key in ['customer_id','product_id']:
    r=q(f"""select count(*) k, avg(n*(mu-0.5)*(mu-0.5))*12 ratio, sum(n) nt from (select {key}, count(*) n, avg(u) mu from w group by 1) where n>=20""")
    print(key, r.to_string())
# by ttype within customer (u within each ttype, customer means)
r=q("""select count(*) k, avg(n*(mu-0.5)*(mu-0.5))*12 ratio from (select customer_id, ttype, count(*) n, avg(u) mu from w group by 1,2) where n>=10""")
print('customer x ttype', r.to_string())
# customers' mean u correlation with income
print(q("select corr(u, inc_q) c_inc, corr(u, cs_q) c_cs, corr(u, bal_q) c_bal, corr(u, h) c_h, corr(u, coalesce(fscore,-1)) c_fs from w").to_string())
