import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('##',t), print(con.execute(s).df().to_string(), '\n'))
q("presence by channel", """select channel, count(*) n, round(avg((lat is not null)::int),4) lat_nn, round(avg((lon is not null)::int),4) lon_nn,
  round(avg((lat is not null and lon is not null)::int),4) both_nn, round(avg((lat is not null or lon is not null)::int),4) any_nn,
  round(avg((branch_id is not null)::int),4) br_nn, round(avg((merchant_name is not null)::int),4) merch_nn, round(avg((city is not null)::int),4) city_nn
  from tx group by 1 order by 1""")
q("lat presence (geo channels) by status / fraud / ttype", """select status, fraud, count(*) n, round(avg((lat is not null)::int),4) lat_nn, round(avg((branch_id is not null)::int),4) br_nn
  from tx where channel in ('POS','ATM','Branch') group by all order by 1,2""")
q("lat presence (geo channels) by ttype", """select ttype, count(*) n, round(avg((lat is not null)::int),4) lat_nn from tx where channel in ('POS','ATM','Branch') group by 1 order by 1""")
q("lat presence (geo channels) by year", """select year(ts) y, count(*) n, round(avg((lat is not null)::int),4) lat_nn from tx where channel in ('POS','ATM','Branch') group by 1 order by 1""")
q("br coordinates near zero", """select country, count(*) n, sum((abs(lat)<1 and abs(lon)<1)::int) near0, sum((abs(lat)<0.2 and abs(lon)<0.2)::int) near0_02,
  round(max(abs(lat)) filter (where abs(lat)<1 and abs(lon)<1),3) max_abs_lat_near0 from br group by 1""")
q("br coords by city", """select country, city, count(*) n, sum((abs(lat)<1 and abs(lon)<1)::int) near0, round(avg(lat),3) mlat, round(min(lat),3) mnlat, round(max(lat),3) mxlat, round(avg(lon),3) mlon
  from br group by all order by 1,2""")
