"""Geo: lat/lon de tx vs centroide de su ciudad, vs sucursal, vs país. ¿Las coordenadas del fraude caen lejos?"""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
con = connect()
print(q(con,"""SELECT fraud, count(*) n, quantile_cont(lat,[0.01,0.25,0.5,0.75,0.99]) qlat, quantile_cont(lon,[0.01,0.25,0.5,0.75,0.99]) qlon FROM tx WHERE lat IS NOT NULL GROUP BY 1"""))
print(q(con,"""SELECT country, fraud, count(*) n, round(avg(lat),2) mlat, round(stddev(lat),2) sdlat, round(avg(lon),2) mlon, round(stddev(lon),2) sdlon FROM tx WHERE lat IS NOT NULL GROUP BY ALL ORDER BY 1,2"""))
print(q(con,"""SELECT city, count(*) n, round(avg(lat),2) mlat, round(stddev(lat),2) sdlat, round(avg(lon),2) mlon, round(stddev(lon),2) sdlon FROM tx WHERE lat IS NOT NULL AND NOT fraud GROUP BY ALL ORDER BY n DESC LIMIT 12"""))
# branch coords vs tx coords
print(q(con,"""SELECT b.country bcountry, t.country, count(*) n, round(avg(b.lat),2) blat, round(avg(t.lat),2) tlat FROM tx t JOIN br b USING(branch_id) WHERE t.lat IS NOT NULL GROUP BY ALL ORDER BY n DESC LIMIT 12"""))
