import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
U="""(select *, (amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) - case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Transfer' then 100 when 'Payment' then 50 when 'Deposit' then 50 else 10 end)
 / (case ttype when 'Purchase' then 495 when 'Withdrawal' then 480 when 'Transfer' then 9900 when 'Payment' then 1950 when 'Deposit' then 4950 else 990 end) u,
 amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) a from tx)"""
# ICC: variance of customer means of u vs expected 1/12/n
q(f"""with c as (select customer_id, count(*) n, avg(u) mu from {U} group by 1 having count(*)>=20)
select count(*) ncust, avg(n) avg_n, var_samp(mu) var_means, avg(1.0/12/n) expected_var_iid, var_samp(mu)/avg(1.0/12/n) ratio from c""")
q(f"""with c as (select product_id, count(*) n, avg(u) mu from {U} group by 1 having count(*)>=20)
select count(*) nprod, avg(n) avg_n, var_samp(mu) var_means, avg(1.0/12/n) expected_var_iid, var_samp(mu)/avg(1.0/12/n) ratio from c""")
# join customer attributes
q(f"""with c as (select customer_id, count(*) n, avg(u) mu, avg(a) ma, sum(a) tot from {U} group by 1)
select cu.segment, count(*) nc, avg(c.n) tx_per_cust, avg(mu) mean_u, avg(ma) mean_amt_usd, median(tot) med_total, avg(cu.income) inc from c join cu using(customer_id) group by all order by 1""")
q(f"""with c as (select customer_id, count(*) n, avg(u) mu from {U} group by 1)
select corr(mu, cu.income) c_inc, corr(mu, cu.credit_score) c_cs, corr(n, cu.income) c_n_inc, corr(n, cu.credit_score) c_n_cs,
 corr(n, datediff('day', cu.registration_date, date '2026-06-17')) c_n_tenure from c join cu using(customer_id)""")
# product attributes vs u
q(f"""with p as (select product_id, count(*) n, avg(u) mu, sum(a) tot from {U} group by 1)
select pr.ptype, count(*) np, avg(p.n) txpp, avg(mu) mu, corr(mu, pr.credit_limit) c_lim, corr(mu, pr.bal) c_bal, corr(p.n, pr.bal) c_n_bal, avg(pr.bal) bal, avg(pr.credit_limit) lim
from p join pr using(product_id) group by all order by np desc""")
# tx count per customer vs cu attributes
q(f"""with c as (select customer_id, count(*) n from tx group by 1)
select cu.cstatus, count(*) nc, avg(n) tx_pc from cu left join c using(customer_id) group by all""")
