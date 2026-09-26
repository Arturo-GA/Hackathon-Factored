"""Distribución de fraud_score en fraude vs legítimas."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd
from fraud_00_common import connect, q
pd.set_option('display.width',200); pd.set_option('display.max_columns',30)
con = connect()
print(q(con, """SELECT fraud, count(*) n, count(fscore) n_score, min(fscore) mn, max(fscore) mx, avg(fscore) avg,
  quantile_cont(fscore,[0.01,0.25,0.5,0.75,0.99]) qs FROM tx GROUP BY 1"""))
# bins de 5
print(q(con, """SELECT CASE WHEN fscore IS NULL THEN -1 ELSE floor(fscore/5)*5 END bin,
  count(*) FILTER (WHERE fraud) fr, count(*) FILTER (WHERE NOT fraud) leg,
  round(100.0*count(*) FILTER (WHERE fraud)/count(*),3) pct_fraud
  FROM tx GROUP BY 1 ORDER BY 1""").to_string())
# precision/decimals
print(q(con, """SELECT fraud, count(*) FILTER (WHERE fscore = round(fscore)) ints,
  count(*) FILTER (WHERE fscore = round(fscore,1)) d1, count(*) FILTER (WHERE fscore=round(fscore,2)) d2, count(fscore) n
  FROM tx GROUP BY 1"""))
# null by fraud
print(q(con, """SELECT fraud, status, count(*) n, round(avg((fscore IS NULL)::int),4) null_rate, avg(fscore) avg FROM tx GROUP BY 1,2 ORDER BY 1,2"""))
