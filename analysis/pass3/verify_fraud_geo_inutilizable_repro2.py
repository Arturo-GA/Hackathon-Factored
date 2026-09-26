"""Verificación independiente de 'fraud_geo_inutilizable' (parte 2: México (0,0), ciudades, país del cliente)."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(t, s):
    print('==', t); print(con.execute(s).df().to_string(index=False), '\n')

# Mexico near (0,0) by tx country; different definitions of "con coordenadas"
q('tx.country=México: % cerca de (0,0)', """
select count(*) filter (where lat is not null) n_lat,
       count(*) filter (where lat is not null and lon is not null) n_both,
       count(*) filter (where lat is not null or lon is not null) n_any,
       round(100*avg((abs(lat)<2 and abs(lon)<2)::int) filter (where lat is not null and lon is not null),2) pct_both_near00_2deg,
       round(100*avg((abs(lat)<2)::int) filter (where lat is not null),2) pct_lat_near0,
       round(100*avg((abs(lon)<2)::int) filter (where lon is not null),2) pct_lon_near0,
       round(100*avg((abs(lat)<=1.0001 and abs(lon)<=1.0001)::int) filter (where lat is not null and lon is not null),2) pct_both_within1deg
from tx where country='México'""")

# all countries: what % of tx with coords are near (0,0)
q('por país de la tx: % cerca de (0,0) (ambas coords)', """
select country, count(*) n_both, round(100*avg((abs(lat)<2 and abs(lon)<2)::int),2) pct_near00,
  round(avg(lat),2) mlat, round(stddev(lat),2) sdlat, round(avg(lon),2) mlon, round(stddev(lon),2) sdlon
from tx where lat is not null and lon is not null group by 1 order by 2 desc""")

# by customer country x tx country
q('país cliente x país tx: centro y dispersión (ambas coords)', """
select cu.country cc, t.country tc, count(*) n,
  round(avg(t.lat),3) mlat, round(stddev(t.lat),3) sdlat, round(min(t.lat),3) minlat, round(max(t.lat),3) maxlat,
  round(avg(t.lon),3) mlon, round(stddev(t.lon),3) sdlon, round(min(t.lon),3) minlon, round(max(t.lon),3) maxlon
from tx t join cu using(customer_id) where t.lat is not null and t.lon is not null group by all order by 1, 3 desc""")

# Colombian cities
q('ciudades colombianas (legítimas y todas): centroide pooled', """
select t.city, count(*) n, round(avg(t.lat),2) mlat, round(stddev(t.lat),2) sdlat, round(avg(t.lon),2) mlon, round(stddev(t.lon),2) sdlon,
  round(100*avg((cu.country<>'Colombia')::int),2) pct_cli_extranj
from tx t join cu using(customer_id) where t.lat is not null and t.country='Colombia' and not t.fraud
group by 1 order by n desc limit 8""")

q('ciudades colombianas SOLO clientes colombianos', """
select t.city, count(*) n, round(avg(t.lat),3) mlat, round(stddev(t.lat),3) sdlat, round(avg(t.lon),3) mlon, round(stddev(t.lon),3) sdlon
from tx t join cu using(customer_id) where t.lat is not null and t.lon is not null and t.country='Colombia' and cu.country='Colombia'
group by 1 order by n desc limit 8""")

q('Tijuana y Querétaro (y otras MX)', """
select t.city, count(*) n, round(avg(t.lat),3) mlat, round(stddev(t.lat),3) sdlat, round(avg(t.lon),3) mlon, round(stddev(t.lon),3) sdlon,
  round(100*avg((cu.country<>'México')::int),2) pct_cli_extranj
from tx t join cu using(customer_id) where t.lat is not null and t.lon is not null and t.country='México'
group by 1 order by n desc limit 10""")

# Does tx city vary with coordinates within a customer country? (city explains lat?)
q('R2 de lat explicado por ciudad de tx vs por país del cliente', """
with d as (select t.city, cu.country cc, t.lat from tx t join cu using(customer_id) where t.lat is not null),
tot as (select var_pop(lat) v from d),
bycity as (select sum(n*v)/sum(n) w from (select city, count(*) n, var_pop(lat) v from d group by 1)),
bycc as (select sum(n*v)/sum(n) w from (select cc, count(*) n, var_pop(lat) v from d group by 1)),
bycc_city as (select sum(n*v)/sum(n) w from (select cc, city, count(*) n, var_pop(lat) v from d group by 1,2))
select round(1-bycity.w/tot.v,4) r2_city, round(1-bycc.w/tot.v,4) r2_custcountry, round(1-bycc_city.w/tot.v,4) r2_cc_plus_city
from tot, bycity, bycc, bycc_city""")
