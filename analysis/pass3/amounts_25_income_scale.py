import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=1; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
K="(case country when 'Argentina' then 350 when 'Colombia' then 4000 else 17 end)"
q(f"""select country, segment, count(*) n, min(income/{K}) mn, quantile_cont(income/{K},0.25) p25, median(income/{K}) med, quantile_cont(income/{K},0.75) p75, max(income/{K}) mx
 from cu group by all order by 2,1""")
# alternative K=1 for Mexico: compare with USD-denominated products of AR/CO customers? product bal by customer country for USD products
q("""select cu.country, p.currency, p.ptype, count(*) n, median(p.bal) med_bal from pr p join cu using(customer_id) where p.ptype in ('Cuenta Ahorro','Tarjeta Crédito') group by all order by 3,1,2""")
# ratio tx monthly volume / income by country
q(f"""with t as (select customer_id, sum(amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end))/36 monthly from tx where ttype in ('Purchase','Withdrawal') group by 1)
 select cu.country, median(t.monthly) med_monthly_usd, median(cu.income) med_income_raw, median(t.monthly/cu.income) ratio_raw, median(t.monthly/(cu.income/{K})) ratio_usd from t join cu using(customer_id) group by 1""")
