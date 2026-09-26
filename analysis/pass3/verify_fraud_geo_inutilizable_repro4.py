"""Verificación independiente de 'fraud_geo_inutilizable' (parte 4: coords de sucursales y fraude por sucursal)."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(t, s):
    d = con.execute(s).df(); print('==', t); print(d.to_string(index=False), '\n'); return d

q('sucursales por ciudad: coords', """
select country, city, count(*) n, round(avg(lat),3) mlat, round(stddev(lat),3) sdlat, round(min(lat),3) minlat, round(max(lat),3) maxlat,
  round(avg(lon),3) mlon, round(min(lon),3) minlon, round(max(lon),3) maxlon,
  sum((abs(lat)<1 and abs(lon)<1)::int) n_null_island
from br group by all order by 1,2""")

q('sucursales null-island vs atributos', """
select (abs(lat)<1 and abs(lon)<1) null_island, branch_type, branch_status, count(*) n from br group by all order by 1,2,3""")

# fraud rate by branch null-island status on ALL tx with branch_id (no coords needed)
base = con.execute("select avg(fraud::int) from tx where branch_id is not null").fetchone()[0]
print('base fraude tx con branch_id', base)
r = q('fraude por tipo de coordenada de sucursal (todas las tx con branch_id)', """
select cu.country cc, (abs(b.lat)<1 and abs(b.lon)<1) br_null_island, count(*) n, sum(t.fraud::int) f, round(1e3*avg(t.fraud::int),3) rate_pm
from tx t join br b using(branch_id) join cu using(customer_id) group by all order by 1,2""")
r = q('fraude por tipo de coordenada de sucursal, pooled y separado por tener coords la tx', """
select (t.lat is not null and t.lon is not null) tx_has_coords, (abs(b.lat)<1 and abs(b.lon)<1) br_null_island, count(*) n, sum(t.fraud::int) f, round(1e3*avg(t.fraud::int),3) rate_pm
from tx t join br b using(branch_id) group by all order by 1,2""")

# fraud rate by branch city (all tx with branch_id)
q('fraude por ciudad de la sucursal (todas las tx con branch_id)', """
select b.country, b.city, count(*) n, sum(t.fraud::int) f, round(1e3*avg(t.fraud::int),3) rate_pm
from tx t join br b using(branch_id) group by all order by 1,2""")

# fraud rate by has coords within channel
q('fraude por tener coords (canales físicos)', """
select channel, (lat is not null) has_lat, count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm
from tx where channel in ('POS','ATM','Branch') group by all order by 1,2""")
q('fraude por patrón de nulos lat/lon (canales físicos)', """
select (lat is not null) has_lat, (lon is not null) has_lon, count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm
from tx where channel in ('POS','ATM','Branch') group by all order by 1,2""")
