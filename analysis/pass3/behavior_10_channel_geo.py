"""Canal vs ttype (¿independientes?), branch_id vs canal, process_date-ts por status, ciudad tx vs ciudad cliente."""
from behavior_common import connect, q
import numpy as np
from scipy.stats import chi2_contingency
con = connect()
def V(df, a, b):
    pv = df.pivot(index=a, columns=b, values='n').fillna(0).values
    chi2 = chi2_contingency(pv)[0]; return np.sqrt(chi2/pv.sum()/(min(pv.shape)-1))
m = q(con, "SELECT ttype, channel, count(*) n FROM tx GROUP BY 1,2"); print("V ttype~channel", round(V(m,'ttype','channel'),4))
m = q(con, "SELECT status, channel, count(*) n FROM tx GROUP BY 1,2"); print("V status~channel", round(V(m,'status','channel'),4))
m = q(con, "SELECT status, ttype, count(*) n FROM tx GROUP BY 1,2"); print("V status~ttype", round(V(m,'status','ttype'),4))
print(q(con, "SELECT channel, count(*) n, avg((branch_id IS NULL)::INT) br_null FROM tx GROUP BY 1"))
print(q(con, """SELECT t.channel, count(*) n, avg((b.branch_id IS NOT NULL)::INT) br_exists, avg((b.city=t.city)::INT) same_city, avg((b.country=t.country)::INT) same_country
   FROM tx t LEFT JOIN br b USING(branch_id) WHERE t.branch_id IS NOT NULL GROUP BY 1"""))
print(q(con, """SELECT status, count(*) n, avg(date_diff('day', ts::DATE, process_date)) lag_mean, min(date_diff('day', ts::DATE, process_date)) mn, max(date_diff('day', ts::DATE, process_date)) mx FROM tx GROUP BY 1"""))
print(q(con, """SELECT date_diff('day', ts::DATE, process_date) lag, count(*) n, avg((status='Pending')::INT) pend, avg((status='Declined')::INT) decl FROM tx GROUP BY 1 ORDER BY 1"""))
print(q(con, """SELECT avg((t.city=c.city)::INT) same_city_as_cust, avg((t.country=c.country)::INT) same_country FROM tx t JOIN cu c USING(customer_id)"""))
print(q(con, """SELECT t.country, count(DISTINCT t.city) ncity, count(*) n FROM tx t GROUP BY 1"""))
# ¿lat/lon consistentes con la ciudad?
print(q(con, """SELECT city, count(*) n, stddev(lat) sdlat, stddev(lon) sdlon, avg(lat) mlat, avg(lon) mlon FROM tx WHERE lat IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 12"""))
