import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
q("select cu.country, p.currency, count(*) n from pr p join cu using(customer_id) group by all order by 1,2")
q("""select currency, ptype, count(*) n, min(bal) mn, median(bal) med, max(bal) mx, median(credit_limit) lim_med, max(credit_limit) lim_max, avg((bal<0)::int) neg from pr group by all order by 2,1""")
q("select country, count(*) n, min(income), median(income) med, max(income), quantile_cont(income,0.9) p90 from cu group by all")
q("select country, segment, median(income) med from cu group by all order by 1,2")
q("select currency, count(*) n, min(claimed), median(claimed) med, max(claimed), avg((claimed is null)::int) nul from cp group by all")
