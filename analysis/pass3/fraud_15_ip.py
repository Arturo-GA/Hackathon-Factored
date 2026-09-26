"""Eventos digitales: IPs compartidas entre clientes, sesiones mixtas anónimo/identificado, y relación con fraude en tx."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from fraud_00_common import connect, q
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
con = connect()
print(q(con,"SELECT ip_address, customer_id, session_id, ts FROM de USING SAMPLE 5 ROWS"))
print(q(con,"""SELECT count(*) n_ip, avg(nc) avg_cust, max(nc) max_cust, count(*) FILTER (WHERE nc>1) ip_multi FROM (SELECT ip_address, count(DISTINCT customer_id) nc FROM de WHERE customer_id IS NOT NULL GROUP BY 1)"""))
print(q(con,"""SELECT count(*) n_cust, avg(ni) avg_ips, median(ni) med_ips FROM (SELECT customer_id, count(DISTINCT ip_address) ni FROM de WHERE customer_id IS NOT NULL GROUP BY 1)"""))
print(q(con,"""SELECT count(*) n_sess, count(*) FILTER (WHERE nc>1) multi_cust, count(*) FILTER (WHERE has_null AND nc>=1) mixed, avg(ne) avg_ev FROM
 (SELECT session_id, count(DISTINCT customer_id) nc, bool_or(customer_id IS NULL) has_null, count(*) ne FROM de GROUP BY 1)"""))
