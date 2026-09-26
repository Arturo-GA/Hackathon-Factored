import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
A="amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"
# monthly trend by currency of median USD-eq and raw
q(f"select year(ts) y, currency, median(amount) med_raw, median({A}) med_eq from tx where ttype='Purchase' group by all order by 2,1")
# hour / dow
q(f"select dayofweek(ts) dow, count(*) n, avg({A}) m from tx where ttype='Transfer' group by 1 order by 1")
q(f"select hour(ts)//6 h, count(*) n, avg({A}) m from tx where ttype='Transfer' group by 1 order by 1")
# product balance vs net flows
q(f"""with f as (select product_id, sum(case when ttype in ('Deposit') then {A} when ttype in ('Withdrawal','Purchase','Payment','Transfer') then -{A} else 0 end) net,
 sum({A}) gross, count(*) n from tx where status='Approved' group by 1)
 select p.ptype, count(*) np, corr(f.net, p.bal/(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)) c_net_bal,
 corr(f.gross, p.bal/(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)) c_gross_bal, avg(f.net) mean_net
 from f join pr p using(product_id) group by all order by np desc""")
# credit card: purchases exceed credit limit?
q(f"""with f as (select product_id, sum({A}) filter (where ttype='Purchase') purch, max({A}) mx from tx where status='Approved' group by 1)
 select count(*) n, avg((f.purch > p.credit_limit/(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end))::int) purch_gt_limit,
 avg((f.mx > p.bal/(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end))::int) maxtx_gt_bal from f join pr p using(product_id) where p.ptype='Tarjeta Crédito'""")
# withdrawals > balance on debit/savings: decline rate
q(f"""select p.ptype, ({A} > p.bal/(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)) over_bal, count(*) n, avg((t.status='Declined')::int) decl, avg((t.code='51')::int) c51
 from tx t join pr p using(product_id) where t.ttype in ('Withdrawal','Purchase','Transfer') and p.ptype in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Débito') group by all order by 1,2""")
# duplicated amount per customer
q("""with d as (select customer_id, amount, count(*) c from tx group by 1,2) select sum(c-1) dup_rows, count(*) filter (where c>1) dup_pairs from d""")
