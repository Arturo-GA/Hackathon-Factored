# H6: tx.branch_id -> ciudad/pais de sucursal = ciudad/pais de tx? lat/lon tx vs sucursal; ciudad cliente
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("""select channel, count(*) n, count(branch_id) nb, count(merchant_name) nm, count(lat) nlat, count(city) ncity from tx group by 1"""))
print(q("""select t.channel, count(*) n, avg((b.branch_id is not null)::int) ex,
   avg((b.city=t.city)::int) same_city, avg((b.country=t.country)::int) same_ctry,
   avg((b.country=c.country)::int) br_eq_cust_ctry, avg((t.city=c.city)::int) tx_city_eq_cust,
   avg((b.city=c.city)::int) br_city_eq_cust
  from (select * from tx where branch_id is not null using sample 300000) t
  left join br b using(branch_id) left join cu c on c.customer_id=t.customer_id group by 1"""))
print(q("select country, count(*) from br group by 1"))
print(q("select country, count(*) from tx group by 1"))
# lat/lon distance tx vs branch
print(q("""select t.channel, count(*) n, median(abs(t.lat-b.lat)+abs(t.lon-b.lon)) med_l1,
   avg((abs(t.lat-b.lat)<0.05 and abs(t.lon-b.lon)<0.05)::int) near
  from (select * from tx where branch_id is not null and lat is not null using sample 300000) t join br b using(branch_id) group by 1"""))
# tx city vs lat/lon: city centroid dispersion
print(q("""select city, count(*) n, stddev(lat) sdlat, stddev(lon) sdlon, avg(lat) mlat, avg(lon) mlon from (select * from tx using sample 300000) where lat is not null group by 1 order by 2 desc limit 12"""))
