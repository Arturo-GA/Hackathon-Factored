import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
A="t.amount/(case t.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"
B="p.bal/(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"
q(f"""select p.ptype, ({A} > {B}) over_bal, count(*) n, avg((t.status='Declined')::int) decl, avg((t.code='51')::int) c51
 from tx t join pr p using(product_id) where t.ttype in ('Withdrawal','Purchase','Transfer') and p.ptype in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Débito') group by all order by 1,2""")
# credit card: amount > credit_limit - bal
q(f"""select ({A} > (p.credit_limit-p.bal)/(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)) over_avail, count(*) n, avg((t.status='Declined')::int) decl, avg((t.code='51')::int) c51
 from tx t join pr p using(product_id) where p.ptype='Tarjeta Crédito' and t.ttype in ('Purchase','Withdrawal') group by all""")
# daily fx vs amount (does the local amount track daily fx?)
q(f"""select t.currency, count(*) n, corr({A}, f.rate) c_eq_rate, corr(t.amount, f.rate) c_raw_rate
 from tx t join fx f on f.date=cast(t.ts as date) and f.src='USD' and f.dst=t.currency where t.ttype='Transfer' group by all""")
# year-level medians with bootstrap-free SE, all ttypes via normalized u
U="""((t.amount/(case t.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) - case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Transfer' then 100 when 'Payment' then 50 when 'Deposit' then 50 else 10 end)
 / (case ttype when 'Purchase' then 495 when 'Withdrawal' then 480 when 'Transfer' then 9900 when 'Payment' then 1950 when 'Deposit' then 4950 else 990 end))"""
q(f"select t.currency, year(ts) y, count(*) n, avg({U}) mean_u, stddev({U})/sqrt(count(*)) se from tx t group by all order by 1,2")
