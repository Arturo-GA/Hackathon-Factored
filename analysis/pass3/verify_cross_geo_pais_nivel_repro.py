# Verificacion independiente: cross_geo_pais_nivel (lat/lon y branch_id de tx sin info geografica real)
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: print(con.execute(s).fetchdf().to_string(), '\n')

import sys
SKIP=int(sys.argv[1]) if len(sys.argv)>1 else 0
print('== 1. lat/lon y branch por canal ==')
q("""select channel, count(*) n, round(100.0*count(*)/sum(count(*)) over(),2) pct_tx,
   round(avg((lat is not null)::int),3) p_lat, round(avg((branch_id is not null)::int),3) p_br,
   round(avg((merchant_name is not null)::int),3) p_merch
 from tx group by 1 order by 2 desc""")
q("""select count(*) n_tot, count(lat) n_lat, round(100.0*count(lat)/count(*),2) pct_lat,
   round(100.0*count(*) filter (where channel in ('ATM','POS','Branch'))/count(*),2) pct_atm_pos_branch
 from tx""")

print('== 2. centros: redondeo de la media por pais de tx, y clusters por celdas de 2 grados ==')
q("""select country, count(*) n, round(avg(lat),3) mlat, round(avg(lon),3) mlon,
   round(min(lat),3) minlat, round(max(lat),3) maxlat, round(min(lon),3) minlon, round(max(lon),3) maxlon
 from tx where lat is not null group by 1 order by 2 desc""")

con.execute("""create temp table g as
 select t.channel, t.country tctry, t.city tcity, c.country cctry, c.city ccity, t.lat, t.lon,
  case when abs(lat)<=1.0001 and abs(lon)<=1.0001 then 'C00'
       when abs(lat-4.711)<=1.01 and abs(lon+74.072)<=1.01 then 'BOG'
       when abs(lat+34.604)<=1.01 and abs(lon+58.382)<=1.01 then 'BUE' else 'otro' end centro
 from tx t join cu c using(customer_id) where t.lat is not null""")
q("select centro, count(*) n, round(100.0*count(*)/sum(count(*)) over(),2) pct from g group by 1 order by 2 desc")
print('-- centro vs pais del cliente / pais de la tx')
q("select cctry, centro, count(*) n, round(100.0*count(*)/sum(count(*)) over(partition by cctry),2) pct from g group by 1,2 order by 1,3 desc")
q("select tctry, centro, count(*) n, round(100.0*count(*)/sum(count(*)) over(partition by tctry),2) pct from g group by 1,2 order by 1,3 desc")
exp = "case cctry when 'Mexico' then 'C00' when 'México' then 'C00' when 'Colombia' then 'BOG' when 'Argentina' then 'BUE' end"
q(f"""select round(avg((centro=({exp}))::int),4) consist_cust_ctry,
   round(avg((centro=(case tctry when 'Mexico' then 'C00' when 'México' then 'C00' when 'Colombia' then 'BOG' when 'Argentina' then 'BUE' end))::int),4) consist_tx_ctry,
   round(avg((tctry=cctry)::int),4) tx_eq_cust_ctry from g""")
print('-- los "otro": que son?')
q("select tctry, cctry, count(*) n, round(avg(lat),2) mlat, round(avg(lon),2) mlon, round(min(lat),2) a, round(max(lat),2) b, round(min(lon),2) c, round(max(lon),2) d from g where centro='otro' group by 1,2 order by 3 desc limit 10")
print('-- ejemplo ciudades de Mexico (tx.city) y su centro')
q("select tcity, centro, count(*) n from g where tctry in ('Mexico','México') group by 1,2 order by 3 desc limit 10")

print('== 3. uniformidad del ruido (C00): deciles de lat y lon, correlacion lat-lon ==')
q("""select quantile_cont(lat,[0.0,0.1,0.25,0.5,0.75,0.9,1.0]) qlat, quantile_cont(lon,[0.0,0.1,0.25,0.5,0.75,0.9,1.0]) qlon,
   round(corr(lat,lon),4) r, round(stddev(lat),4) sdlat, round(1/sqrt(3),4) sd_unif from g where centro='C00'""")
q("""select centro, round(stddev(lat),4) sdlat, round(stddev(lon) filter (where not isnan(lon)),4) sdlon, round(avg(lat),3) mlat from g group by 1""")
print('-- NaN en lon/lat (los otro)')
q("""select centro, count(*) n, sum(isnan(lon)::int) lon_nan, sum(isnan(lat)::int) lat_nan, sum((lon is null)::int) lon_null from g group by 1""")
q("""select channel, count(*) n_lat, round(avg(isnan(lon)::int),4) p_lon_nan from g group by 1""")
print('-- consistencia excluyendo lon NaN')
q(f"""select count(*) n, round(avg((centro=({exp}))::int),5) consist_cust_ctry from g where not isnan(lon)""")
print('-- lat sola por pais del cliente (incluye lon NaN)')
q("""select cctry, round(avg(lat),3) mlat, round(min(lat),3) mn, round(max(lat),3) mx, count(*) n from g group by 1""")
q("""select cctry, round(avg((abs(lat - case cctry when 'México' then 0 when 'Colombia' then 4.711 else -34.604 end)<=1.01)::int),5) lat_in_band from g group by 1""")

print('== 4. sucursales con coordenadas cerca de (0,0) ==')
q("select country, city, count(*) n, round(avg(lat),3) mlat, round(avg(lon),3) mlon, round(max(abs(lat)),3) mxabslat from br group by 1,2 order by 1,2")

print('== 5. branch_id de tx: pais/ciudad ==')
q("""select t.channel, count(*) n, round(avg((b.branch_id is not null)::int),4) exists_br,
   round(avg((b.country=c.country)::int),4) br_ctry_eq_cust, round(avg((b.country=t.country)::int),4) br_ctry_eq_tx,
   round(avg((b.city=t.city)::int),4) br_city_eq_txcity, round(avg((b.city=c.city)::int),4) br_city_eq_custcity
 from tx t left join br b using(branch_id) join cu c on c.customer_id=t.customer_id
 where t.branch_id is not null group by rollup(1) order by 1""")
print('-- azar esperado de br.city=tx.city: sum sobre pais de P(city_br)*P(city_tx)')
q("""with bt as (select t.country, b.city bc, t.city tc from tx t join br b using(branch_id) where t.branch_id is not null),
 pb as (select country, bc city, count(*)*1.0/sum(count(*)) over(partition by country) p from bt group by 1,2),
 pt as (select country, tc city, count(*)*1.0/sum(count(*)) over(partition by country) p from bt group by 1,2),
 w as (select country, count(*)*1.0/sum(count(*)) over() w from bt group by 1)
 select sum(w.w*pb.p*pt.p) expected_same_city from pb join pt using(country, city) join w using(country)""")

print('== 6. dispersion de sucursales por cliente (ATM/Branch, >=5 tx) ==')
q("""with b as (select customer_id, branch_id, count(*) n from tx where branch_id is not null and channel in ('ATM','Branch') group by 1,2),
 c as (select customer_id, sum(n) tot, count(*) nb, max(n) mx from b group by 1)
 select count(*) n_cust, round(avg(tot),2) avg_tx, round(avg(nb),2) avg_distinct_br, round(avg(mx*1.0/tot),4) share_top from c where tot>=5""")
q("""with b as (select customer_id, branch_id, count(*) n from tx where branch_id is not null group by 1,2),
 c as (select customer_id, sum(n) tot, count(*) nb, max(n) mx from b group by 1)
 select count(*) n_cust, round(avg(tot),2) avg_tx, round(avg(nb),2) avg_distinct_br, round(avg(mx*1.0/tot),4) share_top from c where tot>=5""")
print('-- sucursales por pais (para azar esperado)')
q("select country, count(*) n from br group by 1")

print('== 7. estado y tipo de sucursal ==')
q("""select b.branch_status, count(*) n, round(100.0*count(*)/sum(count(*)) over(),2) pct_tx from tx t join br b using(branch_id) group by 1 order by 2 desc""")
q("""select branch_status, count(*) n, round(100.0*count(*)/sum(count(*)) over(),2) pct_br from br group by 1 order by 2 desc""")
q("""with a as (select b.branch_type, count(*) n from tx t join br b using(branch_id) group by 1),
 bb as (select branch_type, count(*) nb from br group by 1)
 select branch_type, n, round(100.0*n/sum(n) over(),2) pct_tx, nb, round(100.0*nb/sum(nb) over(),2) pct_br from a join bb using(branch_type) order by 2 desc""")
print('-- tx en sucursal antes de su apertura / por estado y canal')
q("""select b.branch_status, t.channel, count(*) n, round(avg((cast(t.ts as date) < b.opened)::int),4) before_open from tx t join br b using(branch_id) group by 1,2 order by 1,2""")

print('== 8. aleatoriedad de branch_id dentro del pais del cliente ==')
q("""with bc as (select country, city, count(*)*1.0/sum(count(*)) over(partition by country) p from br group by 1,2),
 t as (select c.country, c.city, b.city bcity from tx t join br b using(branch_id) join cu c on c.customer_id=t.customer_id)
 select count(*) n, round(avg((bcity=t.city)::int),4) obs_same_custcity, round(avg(coalesce(bc.p,0)),4) exp_uniform_branch
 from t left join bc using(country, city)""")
q("""with n as (select b.country, b.branch_id, count(t.transaction_id) n from br b left join tx t using(branch_id) group by 1,2)
 select country, count(*) nbr, min(n) mn, round(avg(n)) mean, max(n) mx, round(stddev(n)/avg(n),4) cv, round(1/sqrt(avg(n)),4) cv_poisson from n group by 1""")
q("select count(*) n_tx_branch, count(*) filter (where b.branch_id is null) sin_match from tx t left join br b using(branch_id) where t.branch_id is not null")
