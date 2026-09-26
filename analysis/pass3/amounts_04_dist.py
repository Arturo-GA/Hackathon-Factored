import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
V="(select *, amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) a from tx)"
for g in ['currency','ttype','channel','status','country','tcat','mcat']:
    q(f"""select {g}, count(*) n, min(a) mn, quantile_cont(a,0.05) p05, quantile_cont(a,0.25) p25, median(a) med, quantile_cont(a,0.75) p75, quantile_cont(a,0.95) p95, max(a) mx, avg(a) mean
      from {V} group by all order by n desc limit 25""")
