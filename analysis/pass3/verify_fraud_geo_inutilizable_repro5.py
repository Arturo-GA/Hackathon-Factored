"""Verificación independiente de 'fraud_geo_inutilizable' (parte 5: reproducción exacta de cortes del original
para explicar diferencias, y distancia a la tx previa)."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(t, s):
    d = con.execute(s).df(); print('==', t); print(d.to_string(index=False), '\n'); return d
base = con.execute("select avg(fraud::int) from tx").fetchone()[0]
# Original definition: equirectangular, WHERE lat not null only (lon null -> km NULL -> ELSE bin)
r = q('cortes del original (lat no nulo; km NULL cae en ELSE)', """
with x as (select t.fraud, (t.lon is null or b.lon is null) km_null,
  111*sqrt(pow(t.lat-b.lat,2)+pow((t.lon-b.lon)*cos(radians(t.lat)),2)) km
  from tx t join br b using(branch_id) where t.lat is not null)
select case when km<100 then 'a<100' when km<500 then 'b<500' when km<1000 then 'c<1000' when km<3000 then 'd<3000' when km<6000 then 'e<6000' else 'f>=6000' end bin,
  count(*) n, sum(fraud::int) f, sum(km_null::int) n_km_null, sum((km_null and fraud)::int) f_km_null from x group by 1 order by 1""")
r['rr'] = (r.f/r.n)/base; print(r.round(3).to_string(index=False), '\n')

# previous tx distance, original definition (immediate previous tx of the customer, any channel)
con.execute("""create temp table s as
select customer_id, fraud, lat, lon, lag(lat) over w plat, lag(lon) over w plon
from tx window w as (partition by customer_id order by ts, transaction_id)""")
# previous tx WITH coordinates: lag within the subset that has both coords
con.execute("""create temp table s2 as
select customer_id, fraud, lat, lon, lag(lat) over w plat_nn, lag(lon) over w plon_nn
from tx where lat is not null and lon is not null window w as (partition by customer_id order by ts, transaction_id)""")
HAV = lambda a, b: f"2*6371*asin(sqrt(pow(sin(radians({a}lat-lat)/2),2)+cos(radians(lat))*cos(radians({a}lat))*pow(sin(radians({b}lon-lon)/2),2)))"
r = q('distancia a tx previa inmediata (haversine; ambas con lat y lon)', f"""
with x as (select fraud, {HAV('p','p')} km from s where lat is not null and lon is not null and plat is not null and plon is not null)
select case when km<10 then 'a<10' when km<50 then 'b<50' when km<100 then 'c<100' when km<200 then 'd<200' when km<1000 then 'e<1000' else 'f>=1000' end bin,
  count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm from x group by 1 order by 1""")
r['rr'] = (r.f/r.n)/base; print(r.round(3).to_string(index=False), '\n')
r = q('distancia equirectangular como el original (<10 km)', """
select count(*) filter (where 111*sqrt(pow(lat-plat,2)+pow((lon-plon)*cos(radians(lat)),2))<10) n_lt10,
       count(*) filter (where 111*sqrt(pow(lat-plat,2)+pow((lon-plon)*cos(radians(lat)),2))<10 and fraud) f_lt10,
       count(*) filter (where lat is not null and plat is not null) n_pairs_lat,
       count(*) filter (where lat is not null and plat is not null and lon is not null and plon is not null) n_pairs_both
from s""")
# expected under iid uniform jitter: simulate
rng = np.random.default_rng(0)
for name, clat in [('MX', 0.0), ('CO', 4.711), ('AR', -34.6037)]:
    m = 2_000_000
    la1, la2 = clat + rng.uniform(-1,1,m), clat + rng.uniform(-1,1,m)
    lo1, lo2 = rng.uniform(-1,1,m), rng.uniform(-1,1,m)
    p1, p2 = np.radians(la1), np.radians(la2)
    d = 2*6371*np.arcsin(np.sqrt(np.sin((p2-p1)/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(np.radians(lo2-lo1)/2)**2))
    print(f'simulación iid U(-1,1) {name}: P(d<10km)={np.mean(d<10):.5f}, P(d<50)={np.mean(d<50):.4f}, P(d<100)={np.mean(d<100):.4f}, P(d>=200)={np.mean(d>=200):.4f}')
print()
r = q('distancia a la última tx previa CON coordenadas (ignora nulos)', f"""
with x as (select fraud, {HAV('p','p').replace('plat','plat_nn').replace('plon','plon_nn')} km from s2 where lat is not null and lon is not null and plat_nn is not null and plon_nn is not null)
select case when km<10 then 'a<10' when km<50 then 'b<50' when km<100 then 'c<100' when km<200 then 'd<200' when km<1000 then 'e<1000' else 'f>=1000' end bin,
  count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm from x group by 1 order by 1""")
r['rr'] = (r.f/r.n)/base; print(r.round(3).to_string(index=False), '\n')
