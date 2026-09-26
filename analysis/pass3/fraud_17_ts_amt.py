"""Artefactos del generador en tx fraude: segundos/minutos exactos, microsegundos, conversión amount_usd, tx antes del registro del cliente."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
con = connect()
print(q(con,"""SELECT fraud, count(*) n, round(100*avg((second(ts)=0)::int),2) pct_s0, round(100*avg((minute(ts)=0 AND second(ts)=0)::int),3) pct_m0,
  round(100*avg((microsecond(ts)%1000000<>0)::int),2) pct_us, round(100*avg((date_part('millisecond',ts)%1000<>0)::int),2) pct_ms FROM tx GROUP BY 1"""))
print(q(con,"""SELECT t.fraud, t.currency, count(*) n, count(t.amount_usd) n_usd, median(t.amount_usd/t.amount) med_ratio, stddev(t.amount_usd/t.amount) sd_ratio,
  median(t.amount_usd/(t.amount*f.rate)) med_vs_fx FROM tx t LEFT JOIN fx f ON f.date=t.ts::date AND f.src=t.currency AND f.dst='USD'
  WHERE t.amount_usd IS NOT NULL GROUP BY ALL ORDER BY 2,1"""))
print(q(con,"""SELECT t.fraud, round(100*avg((t.ts::date < c.registration_date)::int),2) pct_before_reg, round(100*avg((t.ts::date < c.dob)::int),3) pct_before_birth,
 round(100*avg((date_diff('year', c.dob, t.ts::date) < 18)::int),2) pct_minor FROM tx t JOIN cu c USING(customer_id) GROUP BY 1"""))
