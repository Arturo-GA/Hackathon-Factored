import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd
from fraud_00_common import connect, q
pd.set_option('display.width',220); pd.set_option('display.max_colwidth',80)
con = connect()
print(q(con,"SELECT case_type, category, subcategory, count(*) n FROM cp GROUP BY ALL ORDER BY n DESC").to_string())
print(q(con,"SELECT event_type, event_category, count(*) n FROM de GROUP BY ALL ORDER BY n DESC").to_string())
print(q(con,"SELECT ip_country, count(*) n, count(customer_id) nc FROM de GROUP BY ALL ORDER BY n DESC LIMIT 20").to_string())
print(q(con,"SELECT contact_reason, cat, count(*) n FROM cc GROUP BY ALL ORDER BY n DESC").to_string())
