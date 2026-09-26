"""Verificación independiente (reintento) de 'fraud_geo_inutilizable'.
Parte 1: cobertura de lat/lon, ancla empírica por país del cliente, México vs (0,0), centroides por ciudad.
Ejecutar: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_fraud_geo_inutilizable_repro_retry.py
"""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

def show(title, sql):
    d = con.execute(sql).df()
    print('##', title); print(d.to_string(index=False)); print()
    return d

# ---------------------------------------------------------------- 1. cobertura
show('1a cobertura global', """
select count(*) n,
  round(100.0*count(lat)/count(*),2) pct_lat,
  round(100.0*count(lon)/count(*),2) pct_lon,
  round(100.0*count(*) filter (where lat is not null and lon is not null)/count(*),2) pct_ambas,
  round(100.0*count(*) filter (where lat is not null or lon is not null)/count(*),2) pct_alguna,
  round(100.0*count(*) filter (where lat is null and lon is null)/count(*),2) pct_ninguna,
  round(100.0*count(*) filter (where lat is null)/count(*),2) pct_lat_nula
from tx""")
show('1b cobertura por canal', """
select channel, count(*) n, round(100.0*count(*)/sum(count(*)) over (),2) pct_tx,
  round(100.0*count(lat)/count(*),2) pct_lat,
  round(100.0*count(*) filter (where lat is not null and lon is not null)/count(*),2) pct_ambas
from tx group by 1 order by n desc""")

# ---------------------------------------------------------------- 2. ancla empírica
anc = show('2a rango de lat/lon por país del CLIENTE (punto medio = ancla empírica)', """
select cu.country cc, count(t.lat) n_lat, count(t.lon) n_lon,
  round(min(t.lat),4) minlat, round(max(t.lat),4) maxlat, round((min(t.lat)+max(t.lat))/2,4) alat,
  round(min(t.lon),4) minlon, round(max(t.lon),4) maxlon, round((min(t.lon)+max(t.lon))/2,4) alon,
  round(stddev(t.lat),4) sdlat, round(stddev(t.lon),4) sdlon
from tx t join cu using(customer_id)
where t.lat is not null or t.lon is not null group by 1 order by 1""")
show('2b rango de lat/lon por país de la TX (normalizado)', """
select t.country tc, count(t.lat) n_lat,
  round(min(t.lat),3) minlat, round(max(t.lat),3) maxlat, round(avg(t.lat),3) mlat, round(stddev(t.lat),3) sdlat,
  round(min(t.lon),3) minlon, round(max(t.lon),3) maxlon, round(avg(t.lon),3) mlon
from tx t where t.lat is not null group by 1 order by n_lat desc""")

# ancla empírica como tabla temporal
con.execute("""create temp table anc as
select cu.country cc, (min(t.lat)+max(t.lat))/2 alat, (min(t.lon)+max(t.lon))/2 alon
from tx t join cu using(customer_id) where t.lat is not null or t.lon is not null group by 1""")
show('2c regla: |lat-ancla|<=1 y |lon-ancla|<=1 según país del CLIENTE vs según país de la TX', """
with g as (
  select t.lat, t.lon, t.country tc, cu.country cc, a.alat, a.alon, b.alat blat, b.alon blon
  from tx t join cu using(customer_id) join anc a on a.cc=cu.country left join anc b on b.cc=t.country
  where t.lat is not null or t.lon is not null)
select count(*) n_filas_con_alguna_coord,
  round(100.0*avg(((lat is null or abs(lat-alat)<=1.0001) and (lon is null or abs(lon-alon)<=1.0001))::int),3) pct_regla_pais_cliente,
  round(100.0*avg(((lat is null or abs(lat-blat)<=1.0001) and (lon is null or abs(lon-blon)<=1.0001))::int) filter (where blat is not null),3) pct_regla_pais_tx_solo_MX_CO_AR,
  count(*) filter (where tc<>cc) n_tx_foraneas,
  round(100.0*avg(((lat is null or abs(lat-alat)<=1.0001) and (lon is null or abs(lon-alon)<=1.0001))::int) filter (where tc<>cc),3) pct_regla_cliente_en_foraneas
from g""")
show('2d uniformidad del desvío de lat (10 bins de 0.2°) por país cliente', """
select cu.country cc, floor((t.lat-a.alat+1)*5)::int bin, count(*) n
from tx t join cu using(customer_id) join anc a on a.cc=cu.country where t.lat is not null
group by all order by 1,2""").pivot(index='bin', columns='cc', values='n').pipe(print)
print()

# ---------------------------------------------------------------- 3. México cerca de (0,0)
show('3a tx.country=México: % a <2° de (0,0) con varias definiciones', """
select count(lat) n_lat, count(*) filter (where lat is not null and lon is not null) n_ambas,
  round(100*avg((abs(lat)<2 and abs(lon)<2)::int) filter (where lat is not null),3) pct_def_original_lat_no_nula,
  round(100*avg((abs(lat)<2 and abs(lon)<2)::int) filter (where lat is not null and lon is not null),3) pct_ambas_no_nulas,
  round(100*avg((abs(lat)<2)::int) filter (where lat is not null),3) pct_solo_lat
from tx where country='México'""")
show('3b tx.country=México con coords, por país del cliente', """
select cu.country cc, count(*) n, round(100.0*count(*)/sum(count(*)) over (),3) pct,
  round(100*avg((abs(t.lat)<2)::int),2) pct_lat_cerca_0
from tx t join cu using(customer_id) where t.country='México' and t.lat is not null group by 1 order by n desc""")
show('3c clientes MX (cualquier país de tx): % dentro de 1° de (0,0)', """
select count(*) n, round(100*avg((abs(t.lat)<=1.0001 and abs(t.lon)<=1.0001)::int),3) pct_1deg,
  round(avg(t.lat),4) mlat, round(avg(t.lon),4) mlon, round(stddev(t.lat),4) sdlat, round(stddev(t.lon),4) sdlon
from tx t join cu using(customer_id) where cu.country='México' and t.lat is not null and t.lon is not null""")

# ---------------------------------------------------------------- 4. ciudades
show('4a ciudades de tx.country=Colombia (no fraude, lat no nula): centroide y % clientes extranjeros', """
select t.city, count(*) n, round(avg(t.lat),3) mlat, round(stddev(t.lat),3) sdlat, round(avg(t.lon),3) mlon, round(stddev(t.lon),3) sdlon,
  round(100*avg((cu.country<>'Colombia')::int),2) pct_cli_extranjero
from tx t join cu using(customer_id) where t.country='Colombia' and t.lat is not null and not t.fraud
group by 1 order by n desc""")
show('4b mismas ciudades, solo clientes colombianos', """
select t.city, count(*) n, round(avg(t.lat),3) mlat, round(stddev(t.lat),3) sdlat, round(avg(t.lon),3) mlon, round(stddev(t.lon),3) sdlon
from tx t join cu using(customer_id) where t.country='Colombia' and cu.country='Colombia' and t.lat is not null and not t.fraud
group by 1 order by n desc""")
show('4c ciudades de tx.country=México (lat no nula): centroide', """
select t.city, count(*) n, round(avg(t.lat),3) mlat, round(stddev(t.lat),3) sdlat, round(avg(t.lon),3) mlon, round(stddev(t.lon),3) sdlon,
  round(100*avg((cu.country<>'México')::int),2) pct_cli_extranjero
from tx t join cu using(customer_id) where t.country='México' and t.lat is not null
group by 1 order by n desc""")
show('4d ciudades de tx.country=Argentina (lat no nula): centroide', """
select t.city, count(*) n, round(avg(t.lat),3) mlat, round(stddev(t.lat),3) sdlat, round(avg(t.lon),3) mlon, round(stddev(t.lon),3) sdlon,
  round(100*avg((cu.country<>'Argentina')::int),2) pct_cli_extranjero
from tx t join cu using(customer_id) where t.country='Argentina' and t.lat is not null
group by 1 order by n desc""")

# ---------------------------------------------------------------- 5. R2 de lat
show('5 R² de lat explicado por ciudad de la tx, país de la tx y país del cliente', """
with d as (select t.city, t.country tc, cu.country cc, t.lat from tx t join cu using(customer_id) where t.lat is not null),
tot as (select var_pop(lat) v from d),
w_city as (select sum(n*v)/sum(n) w from (select city, count(*) n, var_pop(lat) v from d group by 1)),
w_tc as (select sum(n*v)/sum(n) w from (select tc, count(*) n, var_pop(lat) v from d group by 1)),
w_cc as (select sum(n*v)/sum(n) w from (select cc, count(*) n, var_pop(lat) v from d group by 1))
select round(1-w_city.w/tot.v,4) r2_ciudad_tx, round(1-w_tc.w/tot.v,4) r2_pais_tx, round(1-w_cc.w/tot.v,4) r2_pais_cliente
from tot, w_city, w_tc, w_cc""")
