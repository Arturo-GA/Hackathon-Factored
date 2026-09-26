"""Tasa de fraude por tramo de distancia tx↔sucursal y tx↔centroide de ciudad; calidad de coordenadas (Null Island)."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
con = connect()
b = q(con,"SELECT avg(fraud::int) FROM tx").iloc[0,0]
d = q(con,"""WITH x AS (SELECT t.fraud, 111*sqrt(pow(t.lat-b.lat,2)+pow((t.lon-b.lon)*cos(radians(t.lat)),2)) km FROM tx t JOIN br b USING(branch_id) WHERE t.lat IS NOT NULL)
 SELECT CASE WHEN km<100 THEN 'a<100' WHEN km<500 THEN 'b<500' WHEN km<1000 THEN 'c<1000' WHEN km<3000 THEN 'd<3000' WHEN km<6000 THEN 'e<6000' ELSE 'f>=6000' END bin, count(*) n, sum(fraud::int) f FROM x GROUP BY 1 ORDER BY 1""")
d['rr']=d.f/d.n/b; print(d)
d = q(con,"""SELECT b.country, t.fraud, count(*) n, median(111*sqrt(pow(t.lat-b.lat,2)+pow((t.lon-b.lon)*cos(radians(t.lat)),2))) med_km FROM tx t JOIN br b USING(branch_id) WHERE t.lat IS NOT NULL GROUP BY ALL ORDER BY 1,2"""); print(d)
# Null Island
print(q(con,"""SELECT country, count(*) n_geo, round(100*avg((abs(lat)<2 AND abs(lon)<2)::int),1) pct_near_00 FROM tx WHERE lat IS NOT NULL GROUP BY 1 ORDER BY n_geo DESC"""))
print(q(con,"""SELECT country, round(avg(lat),2) mlat, round(avg(lon),2) mlon, round(stddev(lat),2) sdlat, count(*) n FROM br GROUP BY 1"""))
