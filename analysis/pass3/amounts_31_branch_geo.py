import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=1; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
q("select count(*) n, sum((abs(lat)<1 and abs(lon)<1)::int) at_zero, string_agg(distinct case when abs(lat)<1 and abs(lon)<1 then city end, ', ') cities_zero from br")
q("""select b.country, count(*) n, avg((b.city=cu.city)::int) same_city_as_customer from tx t join br b using(branch_id) join cu using(customer_id) group by 1""")
q("""select b.country, count(distinct b.city) ncities from br b group by 1""")
