import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=1; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
KP="(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"
KC="(case cu.country when 'Argentina' then 350 when 'Colombia' then 4000 else 17 end)"
q(f"""select p.ptype, count(*) n, corr(p.credit_limit/{KP}, cu.income/{KC}) c_lim_inc, corr(p.bal/{KP}, cu.income/{KC}) c_bal_inc, corr(p.credit_limit/{KP}, cu.credit_score) c_lim_cs,
 min(p.credit_limit/{KP}) mnlim, median(p.credit_limit/{KP}) medlim, max(p.credit_limit/{KP}) mxlim, min(p.bal/{KP}) mnbal, median(p.bal/{KP}) medbal, max(p.bal/{KP}) mxbal
 from pr p join cu using(customer_id) group by all order by n desc""")
q(f"""select cu.segment, median(p.credit_limit/{KP}) medlim, avg(p.credit_limit/{KP}) mlim from pr p join cu using(customer_id) where p.ptype='Tarjeta Crédito' group by 1""")
# bal/limit ratio for credit card
q(f"""select min(bal/credit_limit), median(bal/credit_limit), max(bal/credit_limit), corr(bal,credit_limit) from pr where ptype='Tarjeta Crédito'""")
q(f"""select ptype, min(bal/credit_limit), median(bal/credit_limit), max(bal/credit_limit), corr(bal, credit_limit) from pr where credit_limit is not null group by 1""")
