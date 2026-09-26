"""Semántica de la etiqueta fraud: tasa por tipo de tx y estado (¿fraude en depósitos/ajustes/rechazadas?)."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd
from fraud_00_common import connect, q
pd.set_option('display.width',250)
con = connect()
d = q(con,"SELECT ttype, count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm, sum((fraud AND fscore>30)::int) f_hi FROM tx GROUP BY 1 ORDER BY 1"); print(d.to_string(index=False))
d = q(con,"SELECT status, count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm FROM tx GROUP BY 1 ORDER BY 1"); print(d.to_string(index=False))
print(q(con,"SELECT count(*) FILTER (WHERE fraud AND (ttype IN ('Deposit','Adjustment') OR status IN ('Declined'))) f_sin_perdida, count(*) FILTER (WHERE fraud) f FROM tx"))
