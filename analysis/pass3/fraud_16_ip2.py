"""IPs más compartidas; recuperación de customer_id de eventos anónimos vía session_id; IP compartida y fraude."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
con = connect()
print(q(con,"""SELECT ip_address, count(DISTINCT customer_id) nc, count(*) n FROM de WHERE customer_id IS NOT NULL GROUP BY 1 ORDER BY nc DESC LIMIT 8"""))
print(q(con,"""SELECT count(*) FILTER (WHERE ip_address IS NULL) null_ip, count(*) n FROM de"""))
con.execute("""CREATE TEMP TABLE sess AS SELECT session_id, any_value(customer_id) cid, count(DISTINCT customer_id) nc FROM de GROUP BY 1""")
print(q(con,"""SELECT count(*) anon_events, count(*) FILTER (WHERE s.nc=1) recuperables, round(100.0*count(*) FILTER (WHERE s.nc=1)/count(*),1) pct
 FROM de d JOIN sess s USING(session_id) WHERE d.customer_id IS NULL"""))
print(q(con,"""SELECT d.ip_country, c.country, count(*) n FROM de d JOIN sess s USING(session_id) JOIN cu c ON c.customer_id=s.cid WHERE d.customer_id IS NULL AND s.nc=1 GROUP BY ALL ORDER BY n DESC"""))
# eventos de una misma sesión: ¿mismo ip?
print(q(con,"""SELECT count(*) n_sess, count(*) FILTER (WHERE nip>1) multi_ip, count(*) FILTER (WHERE nctry>1) multi_country FROM (SELECT session_id, count(DISTINCT ip_address) nip, count(DISTINCT ip_country) nctry FROM de GROUP BY 1)"""))
