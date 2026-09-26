# H7b: lat/lon de tx dependen solo del pais (centro + ruido uniforme +-1)?  Mexico en (0,0)
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("""select country, count(*) n, count(lat) nlat, round(avg(lat),2) mlat, round(avg(lon),2) mlon, round(min(lat),2) minlat, round(max(lat),2) maxlat,
   round(min(lon),2) minlon, round(max(lon),2) maxlon, round(stddev(lat),3) sdlat from tx group by 1 order by 2 desc"""))
# within Mexico by city: does city change coordinates?
print(q("""select country, city, count(lat) n, round(avg(lat),3) mlat, round(avg(lon),3) mlon, round(stddev(lat),3) sd from tx where lat is not null and country in ('México','Colombia')
 group by 1,2 order by 1,3 desc limit 20"""))
# who has lat: channel x country
print(q("""select channel, avg((lat is not null)::int) p from tx group by 1"""))
