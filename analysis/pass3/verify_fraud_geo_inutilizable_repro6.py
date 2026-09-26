"""Parte 6: ¿el gradiente fraude ~ distancia a la tx previa con coordenadas es real? Controles por país, tiempo y jitter."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(t, s):
    d = con.execute(s).df(); print('==', t); print(d.to_string(index=False), '\n'); return d
con.execute("""create temp table g as
select t.transaction_id, t.customer_id, t.ts, t.fraud, t.fscore, t.channel, t.country tc, cu.country cc, t.lat, t.lon,
  case cu.country when 'Argentina' then -34.6037 when 'Colombia' then 4.711 else 0 end clat,
  case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 else 0 end clon
from tx t join cu using(customer_id) where t.lat is not null and t.lon is not null""")
con.execute("""create temp table s2 as
select *, lag(lat) over w plat, lag(lon) over w plon, lag(fraud) over w pfraud, lag(ts) over w pts,
  lead(lat) over w nlat, lead(lon) over w nlon, lead(fraud) over w nfraud,
  row_number() over w rn, count(*) over (partition by customer_id) ncoord
from g window w as (partition by customer_id order by ts, transaction_id)""")
H = lambda a: f"2*6371*asin(sqrt(pow(sin(radians({a}lat-lat)/2),2)+cos(radians(lat))*cos(radians({a}lat))*pow(sin(radians({a}lon-lon)/2),2)))"
con.execute(f"create temp table s3 as select *, {H('p')} dprev, {H('n')} dnext, date_diff('hour', pts, ts) hgap from s2")

q('fraude por jitter respecto al centro (¿las coords de fraude se generan distinto?)', """
select cc, fraud, count(*) n, round(avg(abs(lat-clat)),4) mean_abs_dlat, round(avg(abs(lon-clon)),4) mean_abs_dlon,
  round(stddev(lat-clat),4) sd_dlat, round(stddev(lon-clon),4) sd_dlon, round(max(abs(lat-clat)),4) max_dlat
from s3 group by all order by 1,2""")

q('fraude por tramo de dprev dentro de país cliente', """
select cc, case when dprev<50 then 'a<50' when dprev<100 then 'b<100' when dprev<150 then 'c<150' else 'd>=150' end bin,
  count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm from s3 where dprev is not null group by all order by 1,2""")

q('fraude por tramo de dnext (distancia a la SIGUIENTE tx con coords) — control simétrico', """
select case when dnext<10 then 'a<10' when dnext<50 then 'b<50' when dnext<100 then 'c<100' when dnext<200 then 'd<200' else 'e>=200' end bin,
  count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm from s3 where dnext is not null group by 1 order by 1""")

q('dprev de la tx previa cuando la tx actual es fraude vs no (¿la previa también es fraude?)', """
select fraud, pfraud, count(*) n, round(avg(dprev),1) mean_dprev, round(median(dprev),1) med_dprev from s3 where dprev is not null group by all order by 1,2""")

q('fraude por tramo de hgap (horas desde la tx previa con coords)', """
select case when hgap<24 then 'a<1d' when hgap<24*7 then 'b<7d' when hgap<24*30 then 'c<30d' when hgap<24*90 then 'd<90d' else 'e>=90d' end bin,
  count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm, round(avg(dprev),1) mean_dprev from s3 where dprev is not null group by 1 order by 1""")

q('fraude por n tx con coords del cliente (¿confusión por actividad?)', """
select case when ncoord<=3 then 'a<=3' when ncoord<=6 then 'b<=6' when ncoord<=10 then 'c<=10' else 'd>10' end bin,
  count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm, round(avg(dprev),1) mean_dprev from s3 group by 1 order by 1""")

q('distancia 0 exacta / muy pequeña a la previa', """
select count(*) filter (where dprev=0) n_zero, count(*) filter (where dprev<1) n_lt1, count(*) filter (where dprev<1 and fraud) f_lt1,
  count(*) filter (where dprev<10) n_lt10, count(*) filter (where dprev<10 and fraud) f_lt10 from s3""")
# export compact dataset for AUC
df = con.execute("select customer_id, cc, fraud::int y, dprev, dnext, abs(lat-clat) adlat, abs(lon-clon) adlon, lat-clat dlat, lon-clon dlon, hgap from s3").df()
df.to_parquet('data/duckdb_tmp/verify_geo_s3.parquet'); print('rows', len(df), 'frauds', df.y.sum())
