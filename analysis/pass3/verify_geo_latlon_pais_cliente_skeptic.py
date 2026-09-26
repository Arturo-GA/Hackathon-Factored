import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('##',t), print(con.execute(s).df().to_string(), '\n'))
CEN="""case cu.country when 'Argentina' then -34.6037 when 'Colombia' then 4.711 when 'México' then 0 when 'Mexico' then 0 end"""
CENL="""case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 when 'México' then 0 when 'Mexico' then 0 end"""
q("cu countries", "select country, count(*) from cu group by 1")
q("tx country values", "select country, count(*) n from tx group by 1 order by 2 desc")
R=f"""(select t.*, cu.country cc, cu.city ccity, {CEN} clat, {CENL} clon from tx t join cu using(customer_id) where t.lat is not null or t.lon is not null)"""
q("rule by customer country", f"""select cc, count(*) n, sum((lat is null)::int) lat_null, sum((lon is null)::int) lon_null,
 sum((abs(lat-clat)<=1.0000001 and abs(lon-clon)<=1.0000001)::int) ok_both,
 sum((abs(lat-clat)<=1.0000001)::int) ok_lat,
 min(lat-clat) mnd, max(lat-clat) mxd, stddev(lat-clat) sdlat, stddev(lon-clon) sdlon, corr(lat-clat, lon-clon) corr_ll
 from {R} group by 1""")
# per customer city: mean offset (is center country or city?)
q("mean offset by customer city", f"""select cc, ccity, count(*) n, round(avg(lat-clat),3) mlat, round(avg(lon-clon),3) mlon from {R} where lon is not null group by all order by cc, n desc""")
# foreign vs domestic: does lat follow tx country?
q("foreign vs domestic", f"""select (country<>cc) foreign_, count(*) n, avg((abs(lat-clat)<=1.0000001 and abs(lon-clon)<=1.0000001)::int) ok
 from {R} where lon is not null group by 1""")
q("foreign by tx country", f"""select cc, country, count(*) n, round(avg(lat),2) mlat, round(avg(lon),2) mlon from {R} where lon is not null and country<>cc group by all order by cc, n desc""")
# within-customer sd
q("within customer sd", f"""with c as (select customer_id, count(*) n, stddev(lat) s from {R} group by 1 having count(*)>=5) select avg(s), count(*) from c""")
# channel presence
q("channel presence", """select channel, count(*) n, avg((lat is not null)::int) lat_nn, avg((lon is not null)::int) lon_nn, avg((branch_id is not null)::int) br_nn,
 avg((lat is not null and lon is null)::int) lat_only, avg((lat is null and lon is not null)::int) lon_only from tx group by 1 order by 1""")
# branch geo
q("branch geo", """select t.channel, (t.country<>cu.country) foreign_, count(*) n, avg((b.branch_id is null)::int) br_missing,
 avg((b.country=cu.country)::int) br_home, avg((b.country=t.country)::int) br_txc, avg((b.city=t.city)::int) br_txcity, avg((b.city=cu.city)::int) br_ccity
 from tx t join cu using(customer_id) join br b on b.branch_id=t.branch_id group by all order by 1,2""")
q("branch_id not in br", "select count(*) n, sum((b.branch_id is null)::int) missing from tx t left join br b using(branch_id) where t.branch_id is not null")
q("br zero coords", "select country, count(*) n, sum((lat=0 and lon=0)::int) zero, sum((abs(lat)<1 and abs(lon)<1)::int) near0 from br group by 1")
q("n cities per country in br", "select country, count(distinct city) from br group by 1")
# country_raw crosstab
q("country_raw x cust country", "pivot (select t.country_raw, cu.country cc from tx t join cu using(customer_id)) on cc using count(*) group by country_raw order by country_raw")
q("country_raw -> country", "select country_raw, country, count(*) n from tx group by all order by 1,2")
q("foreign rate by channel", "select t.channel, avg((t.country<>cu.country)::int) fr, count(*) n from tx t join cu using(customer_id) group by 1 order by 1")
q("domestic city = cust city", "select avg((t.city=cu.city)::int) same, count(*) n from tx t join cu using(customer_id) where t.country=cu.country and t.city is not null")
# does lat/lon carry any signal (fraud / declined)?
q("jitter vs fraud/decline", f"""select ntile5, count(*) n, avg(fraud::int)*1000 fraud_pm, avg((status='Declined')::int) decl from
 (select *, ntile(5) over (order by sqrt((lat-clat)^2+(lon-clon)^2)) ntile5 from {R} where lon is not null) group by 1 order by 1""")
q("lat present vs fraud", """select channel in ('POS','ATM','Branch') geo_ch, (lat is not null) has_lat, count(*) n, avg(fraud::int)*1000 fraud_pm, avg((status='Declined')::int) decl
 from tx group by all order by 1,2""")
