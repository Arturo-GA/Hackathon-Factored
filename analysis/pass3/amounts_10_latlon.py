import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
q("""select country, count(*) n, min(lat), quantile_cont(lat,0.5) mlat, max(lat), min(lon), quantile_cont(lon,0.5) mlon, max(lon), avg((abs(lat)<1 and abs(lon)<1)::int) near0 from tx where lat is not null group by all""")
q("""select country, city, count(*) n, avg(lat) mlat, stddev(lat) sdlat, min(lat) mnlat, max(lat) mxlat, avg(lon) mlon, stddev(lon) sdlon from tx where lat is not null group by all order by 1,2""")
# branch join
q("""select count(*) n, avg((b.branch_id is not null)::int) br_found from tx t left join br b using(branch_id) where t.branch_id is not null""")
q("""select avg((t.city=b.city)::int) same_city, avg((t.country=b.country)::int) same_country, count(*) n,
 avg(case when t.lat is not null then sqrt(pow(t.lat-b.lat,2)+pow(t.lon-b.lon,2)) end) mean_deg_dist,
 median(case when t.lat is not null then sqrt(pow(t.lat-b.lat,2)+pow(t.lon-b.lon,2)) end) med_deg_dist
 from tx t join br b using(branch_id)""")
q("""select b.country bc, t.country tc, count(*) n from tx t join br b using(branch_id) group by all order by n desc limit 12""")
q("select country, city, count(*) n, avg(lat) mlat, avg(lon) mlon, stddev(lat) sdlat from br group by all order by 1,2")
