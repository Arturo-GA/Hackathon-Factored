import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('==',t), print(con.execute(s).df().to_string(), '\n'))
# Independent: compute centers empirically (midrange) per customer country, not assumed
q('lat/lon ranges per customer country', """select cu.country cc, count(*) n_lat, count(t.lon) n_lon, count(*) filter (where t.lon is not null) n_both,
  min(t.lat) lat_min, max(t.lat) lat_max, (min(t.lat)+max(t.lat))/2 lat_mid, avg(t.lat) lat_mean, stddev(t.lat) lat_sd,
  min(t.lon) lon_min, max(t.lon) lon_max, (min(t.lon)+max(t.lon))/2 lon_mid, avg(t.lon) lon_mean, stddev(t.lon) lon_sd
  from tx t join cu using(customer_id) where t.lat is not null group by 1""")
q('lon-only rows (lat null) ranges', """select cu.country cc, count(*) n, min(t.lon), max(t.lon), avg(t.lon), stddev(t.lon)
  from tx t join cu using(customer_id) where t.lat is null and t.lon is not null group by 1""")
# rule check with empirical centers
C = """(select t.*, cu.country cc, cu.city ccity,
  case cu.country when 'Argentina' then -34.6037 when 'Colombia' then 4.7110 when 'México' then 0 end clat,
  case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 when 'México' then 0 end clon
  from tx t join cu using(customer_id))"""
q('rule check (both non-null) by cc and foreign', f"""select cc, (country<>cc) foreign_, count(*) n,
  avg((abs(lat-clat)<=1.00001)::int) lat_ok, avg((abs(lon-clon)<=1.00001)::int) lon_ok,
  avg((abs(lat-clat)<=1.00001 and abs(lon-clon)<=1.00001)::int) both_ok
  from {C} where lat is not null and lon is not null group by all order by 1,2""")
q('rule check total', f"""select count(*) n, sum((abs(lat-clat)<=1.00001 and abs(lon-clon)<=1.00001)::int) ok
  from {C} where lat is not null and lon is not null""")
q('lat-only / lon-only rule', f"""select sum((lat is not null and lon is null)::int) n_lat_only, avg((abs(lat-clat)<=1.00001)::int) filter (where lat is not null and lon is null) ok_lat_only,
  sum((lat is null and lon is not null)::int) n_lon_only, avg((abs(lon-clon)<=1.00001)::int) filter (where lat is null and lon is not null) ok_lon_only from {C}""")
# uniformity: 10 bins of lat offset and lon offset
q('lat offset bins', f"select floor((lat-clat+1)*5)::int b, count(*) n from {C} where lat is not null group by 1 order by 1")
q('lon offset bins', f"select floor((lon-clon+1)*5)::int b, count(*) n from {C} where lon is not null group by 1 order by 1")
q('offset sd and corr', f"select stddev(lat-clat) sd_lat, stddev(lon-clon) sd_lon, corr(lat-clat, lon-clon) corr_ll, 1/sqrt(3) theo from {C} where lat is not null and lon is not null")
# does the tx country centre show up? e.g. foreign tx to USA: is lat near US?
q('foreign by tx country: mean lat/lon', f"""select country tx_country, cc, count(*) n, avg(lat) mlat, avg(lon) mlon
  from {C} where lat is not null and country<>cc group by all order by 1,2""")
# within-customer sd (is center per customer or per country?)
q('within-customer sd', f"""with c as (select customer_id, count(*) n, stddev(lat-clat) s, avg(lat-clat) m from {C} where lat is not null group by 1 having count(*)>=10)
  select count(*) ncust, avg(s) mean_within_sd, stddev(m) sd_of_cust_means, avg(n) from c""")
