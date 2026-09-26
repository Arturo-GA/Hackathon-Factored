import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
C="""(select t.*, cu.country cc from tx t join cu using(customer_id) where lat is not null and not (
 (abs(lat+34.6037)<=1.01 and abs(lon+58.3816)<=1.01) or (abs(lat-4.711)<=1.01 and abs(lon+74.0721)<=1.01) or (abs(lat)<=1.01 and abs(lon)<=1.01)))"""
q(f"select cc, min(lon), quantile_cont(lon,[0.1,0.25,0.5,0.75,0.9]) q, max(lon), min(lat), max(lat) from {C} group by all")
q(f"select cc, round(lon/5)*5 lb, count(*) n from {C} group by all order by 1,2")
# is it lat duplicated into lon? or lon = lat?
q(f"select cc, avg((abs(lon-lat)<1e-9)::int) lon_eq_lat, corr(lat,lon) c from {C} group by all")
q(f"select lat, lon, city, country, cc from {C} using sample 10 rows")
