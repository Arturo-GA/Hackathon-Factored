"""hunt_13: process_date en cc y cp (regla tx = date(ts-6h) cumple 99.999%, cc/cp solo 91.6%): donde falla."""
import duckdb
import pandas as pd
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='300MB'; SET threads=2")
for t in ['cc', 'cp']:
    print(t)
    print(con.execute(f"""SELECT date_diff('day', CAST(ts - INTERVAL 6 HOUR AS DATE), process_date) d, count(*) n FROM {t} GROUP BY 1 ORDER BY 1""").df().T.to_string())
    print(con.execute(f"""SELECT hour(ts) h, avg(date_diff('day', CAST(ts AS DATE), process_date)) lag, 
       avg(CASE WHEN process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE) THEN 1.0 ELSE 0 END) viol FROM {t} GROUP BY 1 ORDER BY 1""").df().T.round(3).to_string())
    print(con.execute(f"""SELECT dayofweek(ts) dow, avg(CASE WHEN process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE) THEN 1.0 ELSE 0 END) viol,
        avg(CASE WHEN dayofweek(process_date) IN (0,6) THEN 1.0 ELSE 0 END) proc_we, count(*) FROM {t} GROUP BY 1 ORDER BY 1""").df().T.round(3).to_string())
print(con.execute("""SELECT dayofweek(process_date) dow, count(*) FROM tx GROUP BY 1 ORDER BY 1""").df().T.to_string())
for t, h in [('tx', 6), ('cc', 8), ('cp', 8), ('tx', 8), ('cc', 6)]:
    print(t, f'process_date = date(ts - {h}h):', con.execute(f"""SELECT count(*), avg(CASE WHEN process_date = CAST(ts - INTERVAL {h} HOUR AS DATE) THEN 1.0 ELSE 0 END) FROM {t}""").fetchone())
for t in ['tx', 'cc']:
    print(t, 'lag por pais del cliente (hora 5 y 7):', con.execute(f"""SELECT c.country, hour(x.ts) h, avg(date_diff('day', CAST(x.ts AS DATE), x.process_date)) lag, count(*)
      FROM {t} x JOIN cu c USING (customer_id) WHERE hour(x.ts) IN (5,6,7,8) GROUP BY 1,2 ORDER BY 1,2""").fetchall())
