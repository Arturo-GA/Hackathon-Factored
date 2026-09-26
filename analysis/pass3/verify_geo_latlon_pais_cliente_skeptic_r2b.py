import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('##',t), print(con.execute(s).df().to_string(), '\n'))
# base: all rows with lat or lon, joined to customer and product
R="""(select t.transaction_id, t.customer_id, t.channel, t.ttype, t.status, t.fraud, t.country tc, t.city tcity, t.lat, t.lon, t.currency,
   cu.country cc, cu.city ccity, p.currency pcur,
   case cu.country when 'Argentina' then -34.6037 when 'Colombia' then 4.711 else 0 end clat,
   case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 else 0 end clon
 from tx t join cu using(customer_id) left join pr p on p.product_id=t.product_id
 where t.lat is not null or t.lon is not null)"""
con.execute(f"create temp table g as select * from {R}")
q("n rows with any coord / both / lat-only / lon-only", """select count(*) any_, sum((lat is not null and lon is not null)::int) both_,
  sum((lat is not null and lon is null)::int) lat_only, sum((lat is null and lon is not null)::int) lon_only from g""")
q("rule by customer country (lat and lon separately, eps 1e-9)", """select cc, count(*) n,
  sum((lat is not null and lon is not null)::int) n_both,
  avg((abs(lat-clat)<=1+1e-9)::int) filter (where lat is not null) lat_ok,
  avg((abs(lon-clon)<=1+1e-9)::int) filter (where lon is not null) lon_ok,
  round(min(lat-clat),5) mn_dlat, round(max(lat-clat),5) mx_dlat, round(min(lon-clon),5) mn_dlon, round(max(lon-clon),5) mx_dlon,
  round((min(lat)+max(lat))/2,4) mid_lat, round((min(lon)+max(lon))/2,4) mid_lon, round(avg(lat),4) mean_lat, round(avg(lon),4) mean_lon,
  round(stddev(lat-clat),4) sd_dlat, round(stddev(lon-clon),4) sd_dlon, round(corr(lat-clat,lon-clon),4) corr_d
  from g group by 1 order by 1""")
q("center by customer country x product currency (USD-product confound)", """select cc, pcur, count(*) n,
  avg((abs(lat-clat)<=1+1e-9 and abs(lon-clon)<=1+1e-9)::int) filter (where lat is not null and lon is not null) ok,
  round(avg(lat),3) mlat, round(avg(lon),3) mlon from g group by all order by 1,2""")
q("foreign vs domestic", """select (tc<>cc) foreign_, count(*) n,
  avg((abs(lat-clat)<=1+1e-9 and abs(lon-clon)<=1+1e-9)::int) filter (where lat is not null and lon is not null) ok_home
  from g group by 1""")
q("foreign rows: mean coords by customer country x tx country", """select cc, tc, count(*) n, round(avg(lat),2) mlat, round(avg(lon),2) mlon
  from g where tc<>cc group by all order by 1,2""")
q("mean offset by customer city (center depends on city?)", """select cc, ccity, count(*) n, round(avg(lat-clat),3) mdlat, round(avg(lon-clon),3) mdlon
  from g group by all order by 1, n desc""")
q("mean offset by tx city (domestic, top)", """select cc, tcity, count(*) n, round(avg(lat-clat),3) mdlat, round(avg(lon-clon),3) mdlon
  from g where tc=cc group by all order by 1, n desc limit 20""")
q("within-customer SD (per-tx jitter vs per-customer home)", """with c as (select customer_id, count(*) n, stddev(lat) s, stddev(lon) sl from g group by 1 having count(*)>=5)
  select round(avg(s),4) mean_within_sd_lat, round(avg(sl),4) mean_within_sd_lon, count(*) ncust from c""")
q("uniformity lat offset, 10 bins", """select floor((lat-clat+1)*5)::int b, count(*) n from g where lat is not null group by 1 order by 1""")
q("uniformity lon offset, 10 bins", """select floor((lon-clon+1)*5)::int b, count(*) n from g where lon is not null group by 1 order by 1""")
q("corner test (indep uniform square => 0.04, disk => 0)", """select avg((abs(lat-clat)>0.8 and abs(lon-clon)>0.8)::int) corner, avg((sqrt((lat-clat)^2+(lon-clon)^2)>1)::int) outside_unit_disk
  from g where lat is not null and lon is not null""")
q("decimals of lat (rounded?)", """select length(split_part(cast(lat as varchar),'.',2)) ndec, count(*) n from g where lat is not null group by 1 order by 1""")
