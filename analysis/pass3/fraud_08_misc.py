"""Hipótesis varias: formato de ID, retraso process_date, redondeo de monto, geo presente, monto vs saldo/límite, tipos de producto."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
con = connect()
print(q(con,"SELECT transaction_id, fraud FROM tx USING SAMPLE 5 ROWS"))
print(q(con,"""SELECT fraud, count(*) n, min(transaction_id) mn, max(transaction_id) mx,
  avg(TRY_CAST(regexp_extract(transaction_id,'([0-9]+)$',1) AS BIGINT)) avg_num, median(TRY_CAST(regexp_extract(transaction_id,'([0-9]+)$',1) AS BIGINT)) med_num FROM tx GROUP BY 1"""))
print(q(con,"""SELECT fraud, date_diff('day', ts::date, process_date) lag, count(*) n FROM tx GROUP BY ALL ORDER BY 1,2""").pivot(index='lag',columns='fraud',values='n').assign(r=lambda x: x[True]/x[True].sum()/(x[False]/x[False].sum())).head(15))
print(q(con,"""SELECT fraud, round(100*avg((amount=round(amount))::int),2) pct_int, round(100*avg((amount=round(amount,-1))::int),2) pct_10,
   round(100*avg((amount=round(amount,-2))::int),2) pct_100, round(100*avg((lat IS NOT NULL)::int),2) pct_geo,
   round(100*avg((merchant_name IS NOT NULL)::int),2) pct_merch, round(100*avg((city IS NOT NULL)::int),2) pct_city,
   round(100*avg((amount<0)::int),2) pct_neg, median(amount) med_amt, avg(ln(1+abs(amount))) avg_logamt FROM tx GROUP BY 1"""))
print(q(con,"""SELECT t.fraud, round(100*avg((t.amount>p.bal)::int),2) pct_gt_bal, round(100*avg((t.amount>p.credit_limit)::int),2) pct_gt_lim,
   round(100*avg((t.ts < p.opened)::int),3) pct_before_open, round(100*avg((t.ts::date > p.expires)::int),3) pct_after_exp,
   round(100*avg((t.ts > p.last_tx)::int),3) pct_after_lasttx, round(100*avg((t.customer_id<>p.customer_id)::int),3) pct_owner_diff
   FROM tx t JOIN pr p USING(product_id) GROUP BY 1"""))
# ¿fraude por tipo de producto con denominador?
d = q(con,"""SELECT p.ptype, count(*) n, sum(t.fraud::int) f, round(1e3*avg(t.fraud::int),3) rate_pm FROM tx t JOIN pr p USING(product_id) GROUP BY 1 ORDER BY 1""")
print(d.to_string(index=False))
