"""¿El autorizador usa fraud_score? Tasa de Declined/Reversed y códigos por tramo de fscore (legítimas y fraude)."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
con = connect()
print(q(con,"""SELECT CASE WHEN fscore IS NULL THEN 'nulo' WHEN fscore<=10 THEN '00-10' WHEN fscore<=20 THEN '10-20' WHEN fscore<=30 THEN '20-30' WHEN fscore<=60 THEN '30-60' ELSE '60-100' END tramo,
  count(*) n, round(100*avg((status='Declined')::int),2) pct_decl, round(100*avg((status='Reversed')::int),2) pct_rev, round(100*avg((status='Pending')::int),2) pct_pend,
  round(100*avg((code='05')::int),2) c05, round(100*avg((code='14')::int),2) c14, round(100*avg((code='51')::int),2) c51, round(100*avg((code='54')::int),2) c54
  FROM tx GROUP BY 1 ORDER BY 1"""))
print(q(con,"""SELECT corr(fscore, ln(1+amount)) r_amt, corr(fscore, hour(ts)) r_hr FROM tx WHERE NOT fraud AND fscore IS NOT NULL"""))
