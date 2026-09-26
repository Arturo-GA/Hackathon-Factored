import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('##',t), print(con.execute(s).df().to_string(), '\n'))
CENL="""case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 else 0 end"""
q("lon-only rows rule", f"""select cu.country, count(*) n, avg((abs(t.lon-{CENL})<=1.0000001)::int) ok from tx t join cu using(customer_id) where t.lat is null and t.lon is not null group by 1""")
q("br coords by city", """select country, city, count(*) n, round(avg(lat),2) mlat, round(min(lat),2) mnlat, round(max(lat),2) mxlat, round(avg(lon),2) mlon from br group by all order by 1,2""")
q("MX cust with raw Mexico: city", """select t.country_raw, count(*) n, avg((t.city=cu.city)::int) same_city, avg((t.city is null)::int) city_null
 from tx t join cu using(customer_id) where cu.country='México' group by 1""")
q("domestic city mismatch source", """select t.country_raw, count(*) n, avg((t.city<>cu.city)::int) diffcity from tx t join cu using(customer_id) where t.country=cu.country and t.city is not null group by 1""")
q("foreign total & with coords", """select count(*) n, sum((t.lat is not null)::int) lat_nn, sum((t.lat is not null and t.lon is not null)::int) both_nn from tx t join cu using(customer_id) where t.country<>cu.country""")
q("coords presence overall", "select sum((lat is not null)::int) lat, sum((lat is not null and lon is not null)::int) both_, sum((lat is not null or lon is not null)::int) any_ from tx")
