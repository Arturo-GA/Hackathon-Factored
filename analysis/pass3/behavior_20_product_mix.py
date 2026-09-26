"""Mezcla de productos por cliente: ptype vs segmento/edad/país; vigencia (expires-opened) por ptype; dpd por ptype; pstatus vs cstatus."""
from behavior_common import connect, q
import numpy as np
from scipy.stats import chi2_contingency
con = connect()
def V(sql, a, b):
    m = q(con, sql); pv = m.pivot(index=a, columns=b, values='n').fillna(0).values
    return np.sqrt(chi2_contingency(pv)[0]/pv.sum()/(min(pv.shape)-1))
print("V ptype~segment", round(V("SELECT p.ptype, c.segment, count(*) n FROM pr p JOIN cu c USING(customer_id) GROUP BY 1,2", 'ptype','segment'),4))
print("V ptype~country", round(V("SELECT p.ptype, c.country, count(*) n FROM pr p JOIN cu c USING(customer_id) GROUP BY 1,2", 'ptype','country'),4))
print("V pstatus~cstatus", round(V("SELECT p.pstatus, c.cstatus, count(*) n FROM pr p JOIN cu c USING(customer_id) GROUP BY 1,2", 'pstatus','cstatus'),4))
print("V ptype~pstatus", round(V("SELECT ptype, pstatus, count(*) n FROM pr GROUP BY 1,2", 'ptype','pstatus'),4))
print("V opening_channel~ptype", round(V("SELECT ptype, opening_channel, count(*) n FROM pr GROUP BY 1,2", 'ptype','opening_channel'),4))
print(q(con, """SELECT CASE WHEN date_diff('year', c.dob, DATE '2026-06-17')<25 THEN '<25' WHEN date_diff('year', c.dob, DATE '2026-06-17')<60 THEN '25-59' ELSE '60+' END age, c.segment='Student' student,
   count(*) n, avg((p.ptype='Préstamo Hipotecario')::INT) hip, avg((p.ptype='Inversión')::INT) inv, avg((p.ptype='Tarjeta Crédito')::INT) tc FROM pr p JOIN cu c USING(customer_id) GROUP BY 1,2 ORDER BY 1,2"""))
print(q(con, """SELECT ptype, count(*) n, avg((expires IS NULL)::INT) exp_null, quantile_cont(date_diff('month', opened, expires),[0,0.5,1]) mths FROM pr GROUP BY 1 ORDER BY 1"""))
print(q(con, """SELECT ptype, avg((dpd>0)::INT) dpd_pos, max(dpd) mx, avg((dpd IS NULL)::INT) dpd_null FROM pr GROUP BY 1 ORDER BY 1"""))
print(q(con, """SELECT c.cstatus, count(*) n, avg((p.pstatus='Active')::INT) act, avg((p.pstatus='Closed')::INT) closed FROM pr p JOIN cu c USING(customer_id) GROUP BY 1"""))
print(q(con, "SELECT nprod, count(*) FROM (SELECT c.customer_id, count(p.product_id) nprod FROM cu c LEFT JOIN pr p USING(customer_id) GROUP BY 1) GROUP BY 1 ORDER BY 1"))
print(q(con, "SELECT segment, count(*) n, quantile_cont(date_diff('year', dob, DATE '2026-06-17'),[0,0.5,1]) age_q, avg((occupation ILIKE '%estudiante%')::INT) occ_est FROM cu GROUP BY 1"))
print(q(con, "SELECT occupation, count(*) n FROM cu GROUP BY 1 ORDER BY 2 DESC LIMIT 20"))
