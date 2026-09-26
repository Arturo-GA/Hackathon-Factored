import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
R="""(select t.*, cu.country cc, cu.city ccity,
 case cu.country when 'Argentina' then -34.6037 when 'Colombia' then 4.711 else 0 end clat,
 case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 else 0 end clon
 from tx t join cu using(customer_id) where lat is not null)"""
q(f"""select cc, count(*) n, avg((lon is null)::int) lon_null,
 avg((abs(lat-clat)<=1.0001 and abs(lon-clon)<=1.0001)::int) filter (where lon is not null) rule_ok,
 min(lat-clat), max(lat-clat), stddev(lat-clat) from {R} group by all""")
# per-customer jitter variance
q(f"""with c as (select customer_id, count(*) n, stddev(lat) s from {R} group by 1 having count(*)>=5) select avg(s) mean_within_sd, count(*) from c""")
# jitter uniform?
q(f"select floor((lat-clat+1)*5) b, count(*) n from {R} group by 1 order by 1")
# customer city vs tx city
q("""select avg((t.city=cu.city)::int) same_city, avg((t.country=cu.country)::int) same_country, count(*) from tx t join cu using(customer_id) where t.city is not null""")
q("select country, count(*) n from cu group by all")
# channel presence of lat
q("select channel, avg((lat is not null)::int) latnn, avg((lon is not null)::int) lonnn from tx group by 1")
