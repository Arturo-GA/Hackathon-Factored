"""Features secuenciales por cliente (y por producto): tiempo desde tx previa, cambio país/ciudad,
distancia, primera vez con comercio/canal/ciudad, monto vs historial, etc."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',200)
con = connect()
con.execute("""CREATE TEMP TABLE s AS
SELECT transaction_id, customer_id, product_id, ts, fraud, fscore, amount, channel, country, city, merchant_name, mcat, ttype, lat, lon,
  date_diff('second', lag(ts) OVER w, ts)/3600.0 h_prev_c,
  date_diff('second', ts, lead(ts) OVER w)/3600.0 h_next_c,
  lag(country) OVER w prev_country, lag(city) OVER w prev_city, lag(lat) OVER w plat, lag(lon) OVER w plon,
  lag(channel) OVER w prev_channel,
  lag(fraud) OVER w prev_fraud, lead(fraud) OVER w next_fraud,
  row_number() OVER w rn, count(*) OVER (PARTITION BY customer_id) n_c,
  row_number() OVER (PARTITION BY customer_id, merchant_name ORDER BY ts, transaction_id) rn_merch,
  row_number() OVER (PARTITION BY customer_id, channel ORDER BY ts, transaction_id) rn_chan,
  row_number() OVER (PARTITION BY customer_id, city ORDER BY ts, transaction_id) rn_city,
  row_number() OVER (PARTITION BY customer_id, country ORDER BY ts, transaction_id) rn_country,
  date_diff('second', lag(ts) OVER wp, ts)/3600.0 h_prev_p,
  row_number() OVER wp rn_p, count(*) OVER (PARTITION BY product_id) n_p,
  avg(amount) OVER (PARTITION BY customer_id) mean_amt_c
FROM tx WINDOW w AS (PARTITION BY customer_id ORDER BY ts, transaction_id), wp AS (PARTITION BY product_id ORDER BY ts, transaction_id)""")
print('built')
base = q(con,"SELECT avg(fraud::int) b, count(*) n FROM s"); print(base)
b = base.b[0]
def rate(expr, name):
    d = q(con, f"SELECT {expr} v, count(*) n, sum(fraud::int) f FROM s GROUP BY 1 ORDER BY 1")
    d['rate_pm']=1e3*d.f/d.n; d['rr']=(d.f/d.n)/b
    print('\n==',name); print(d.to_string(index=False))
rate("CASE WHEN h_prev_c IS NULL THEN 'first' WHEN h_prev_c<0.0167 THEN '<1min' WHEN h_prev_c<1 THEN '<1h' WHEN h_prev_c<24 THEN '<24h' WHEN h_prev_c<24*7 THEN '<7d' WHEN h_prev_c<24*30 THEN '<30d' ELSE '>=30d' END", 'horas desde tx previa del cliente')
rate("CASE WHEN h_next_c IS NULL THEN 'last' WHEN h_next_c<0.0167 THEN '<1min' WHEN h_next_c<1 THEN '<1h' WHEN h_next_c<24 THEN '<24h' WHEN h_next_c<24*7 THEN '<7d' WHEN h_next_c<24*30 THEN '<30d' ELSE '>=30d' END", 'horas hasta tx siguiente')
rate("CASE WHEN prev_country IS NULL THEN 'first' WHEN prev_country=country THEN 'same' ELSE 'diff' END", 'país vs tx previa')
rate("CASE WHEN prev_city IS NULL THEN 'null' WHEN prev_city=city THEN 'same' ELSE 'diff' END", 'ciudad vs tx previa')
rate("CASE WHEN prev_channel IS NULL THEN 'first' WHEN prev_channel=channel THEN 'same' ELSE 'diff' END", 'canal vs tx previa')
rate("CASE WHEN rn_merch=1 AND merchant_name IS NOT NULL THEN 'first_merch' WHEN merchant_name IS NULL THEN 'nomerch' ELSE 'repeat' END", 'primera vez con comercio')
rate("CASE WHEN rn_chan=1 THEN 'first' ELSE 'repeat' END", 'primera vez con canal')
rate("CASE WHEN city IS NULL THEN 'null' WHEN rn_city=1 THEN 'first' ELSE 'repeat' END", 'primera vez con ciudad')
rate("CASE WHEN rn_country=1 THEN 'first' ELSE 'repeat' END", 'primera vez con país')
rate("CASE WHEN rn<=1 THEN '1' WHEN rn<=5 THEN '2-5' WHEN rn<=20 THEN '6-20' WHEN rn<=50 THEN '21-50' ELSE '>50' END", 'orden de tx del cliente')
rate("CASE WHEN n_c<=5 THEN 'a<=5' WHEN n_c<=20 THEN 'b<=20' WHEN n_c<=50 THEN 'c<=50' WHEN n_c<=100 THEN 'd<=100' ELSE 'e>100' END", 'n tx del cliente')
rate("CASE WHEN plat IS NULL OR lat IS NULL THEN 'nogeo' ELSE CASE WHEN 111*sqrt(pow(lat-plat,2)+pow((lon-plon)*cos(radians(lat)),2))<10 THEN '<10km' WHEN 111*sqrt(pow(lat-plat,2)+pow((lon-plon)*cos(radians(lat)),2))<100 THEN '<100km' WHEN 111*sqrt(pow(lat-plat,2)+pow((lon-plon)*cos(radians(lat)),2))<1000 THEN '<1000km' ELSE '>=1000km' END END", 'distancia a tx previa')
rate("CASE WHEN mean_amt_c IS NULL OR mean_amt_c=0 THEN 'na' WHEN amount/mean_amt_c<0.25 THEN 'a<0.25' WHEN amount/mean_amt_c<0.5 THEN 'b<0.5' WHEN amount/mean_amt_c<1 THEN 'c<1' WHEN amount/mean_amt_c<2 THEN 'd<2' WHEN amount/mean_amt_c<4 THEN 'e<4' ELSE 'f>=4' END", 'monto / media del cliente')
rate("CASE WHEN prev_fraud IS NULL THEN 'first' WHEN prev_fraud THEN 'prev_fraud' ELSE 'prev_ok' END", 'tx previa del cliente es fraude')
rate("CASE WHEN h_prev_p IS NULL THEN 'first' WHEN h_prev_p<1 THEN '<1h' WHEN h_prev_p<24 THEN '<24h' WHEN h_prev_p<24*7 THEN '<7d' ELSE '>=7d' END", 'horas desde tx previa del producto')
rate("hour(ts) BETWEEN 0 AND 5", 'noche 0-5h')
# fraud with low / null score only
print('\n### solo fraude con fscore<=30 o nulo vs legítimas')
b2 = q(con,"SELECT avg(fraud::int) FROM s WHERE coalesce(fscore,0)<=30").iloc[0,0]
for expr,name in [("CASE WHEN h_prev_c IS NULL THEN 'first' WHEN h_prev_c<1 THEN '<1h' WHEN h_prev_c<24 THEN '<24h' WHEN h_prev_c<24*7 THEN '<7d' ELSE '>=7d' END",'h prev'),
                  ("CASE WHEN prev_country IS NULL THEN 'first' WHEN prev_country=country THEN 'same' ELSE 'diff' END",'pais prev'),
                  ("CASE WHEN rn_merch=1 AND merchant_name IS NOT NULL THEN 'first_merch' WHEN merchant_name IS NULL THEN 'nomerch' ELSE 'repeat' END",'first merch')]:
    d = q(con, f"SELECT {expr} v, count(*) n, sum(fraud::int) f FROM s WHERE coalesce(fscore,0)<=30 GROUP BY 1 ORDER BY 1")
    d['rr']=(d.f/d.n)/b2; print('==',name); print(d.to_string(index=False))
