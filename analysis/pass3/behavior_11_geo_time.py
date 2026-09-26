"""(a) process_date = fecha(ts - 6h)? (b) lat/lon por país y ciudad: ¿coordenadas coherentes?"""
from behavior_common import connect, q
con = connect()
print(q(con, "SELECT avg((process_date = (ts - INTERVAL 6 HOUR)::DATE)::INT) rule_6h, avg((process_date = ts::DATE)::INT) same_date, count(*) FROM tx"))
for t in ['cc']:
    print(t, q(con, f"SELECT avg((process_date = (ts - INTERVAL 6 HOUR)::DATE)::INT) rule_6h, avg((process_date = ts::DATE)::INT) same_date, min(ts), max(ts) FROM {t}"))
print(q(con, """SELECT country, count(*) n, avg((lat IS NULL)::INT) null_ll, quantile_cont(lat,[0.01,0.5,0.99]) lat_q, quantile_cont(lon,[0.01,0.5,0.99]) lon_q FROM tx GROUP BY 1"""))
print(q(con, """SELECT country, city, count(*) n, quantile_cont(lat,[0.05,0.5,0.95]) lat_q, quantile_cont(lon,[0.05,0.5,0.95]) lon_q FROM tx WHERE country IN ('México','Colombia','Argentina') GROUP BY 1,2 ORDER BY 1,2"""))
print(q(con, "SELECT country, city, avg(lat) lat, avg(lon) lon FROM br GROUP BY 1,2 ORDER BY 1,2"))
