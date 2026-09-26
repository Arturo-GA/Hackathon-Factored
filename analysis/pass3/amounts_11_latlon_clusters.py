import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
C="""(select *, case when abs(lat+34.6037)<=1.01 and abs(lon+58.3816)<=1.01 then 'BuenosAires'
 when abs(lat-4.711)<=1.01 and abs(lon+74.0721)<=1.01 then 'Bogota'
 when abs(lat)<=1.01 and abs(lon)<=1.01 then 'Zero' else 'Other' end cl from tx where lat is not null)"""
q(f"select cl, count(*) n, min(lat-case cl when 'BuenosAires' then -34.6037 when 'Bogota' then 4.711 else 0 end) mndl, max(lat-case cl when 'BuenosAires' then -34.6037 when 'Bogota' then 4.711 else 0 end) mxdl, stddev(lat) from {C} group by all")
q(f"pivot (select country, cl from {C}) on cl using count(*) group by country")
q(f"pivot (select country, coalesce(city,'NULL') city, cl from {C}) on cl using count(*) group by country, city order by country, city")
q(f"pivot (select country_raw, cl from {C}) on cl using count(*) group by country_raw")
# customer country vs cluster
q(f"pivot (select cu.country cc, cl from {C} t join cu using(customer_id)) on cl using count(*) group by cc")
