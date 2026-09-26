import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
# normalized position within ttype range: u in [0,1]
U="""(select *, (amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) - case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Transfer' then 100 when 'Payment' then 50 when 'Deposit' then 50 else 10 end)
 / (case ttype when 'Purchase' then 495 when 'Withdrawal' then 480 when 'Transfer' then 9900 when 'Payment' then 1950 when 'Deposit' then 4950 else 990 end) u from tx)"""
q(f"select status, code, count(*) n, avg(u) mean_u, quantile_cont(u,0.9) p90 from {U} group by all order by 1,2")
q(f"select fraud, count(*) n, avg(u) mean_u, quantile_cont(u,0.9) p90 from {U} group by all")
q(f"select (fscore>=50) hi, count(*) n, avg(u) mean_u, corr(u,fscore) c from {U} where fscore is not null group by all")
q(f"select corr(u,fscore) from {U}")
# top decile vs rest: decline rate
q(f"select floor(u*5)/5 ub, count(*) n, avg((status='Declined')::int) decl, avg((code='51')::int) c51, avg(fraud::int)*1000 fraud_pm from {U} group by all order by 1")
# adjustment deep look
q("""select status, count(*) n, avg(amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)) m from tx where ttype='Adjustment' group by all""")
q("""select channel, tcat is null tn, mcat is null mn, count(*) n from tx where ttype='Adjustment' group by all order by n desc""")
