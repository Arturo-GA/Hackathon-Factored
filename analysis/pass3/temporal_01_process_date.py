"""H1: relación ts vs process_date. ¿process_date = fecha local de ts - offset fijo? ¿Por país?
Se prueba process_date == CAST(ts - INTERVAL k HOUR AS DATE) para k=0..8 en tx, cc, cp, sv."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

for t in ['tx', 'cc', 'cp', 'sv']:
    cols = ", ".join([f"avg((process_date = CAST(ts - INTERVAL {k} HOUR AS DATE))::INT) k{k}" for k in range(0, 9)])
    print(t, con.execute(f"SELECT count(*) n, {cols} FROM {t} WHERE ts IS NOT NULL AND process_date IS NOT NULL").fetchdf().round(4).to_string(index=False))

print(con.execute("""SELECT country, count(*) n,
  avg((process_date = CAST(ts - INTERVAL 6 HOUR AS DATE))::INT) k6,
  sum((process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE))::INT) n_excep,
  avg((process_date < ts::DATE)::INT) share_ts_after
  FROM tx GROUP BY 1 ORDER BY 1""").fetchdf().to_string(index=False))
print("excepciones tx a k=6:")
print(con.execute("""SELECT ts, process_date, country, ttype, status FROM tx
   WHERE process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE) LIMIT 15""").fetchdf().to_string(index=False))
print(con.execute("""SELECT count(*) n_excep, min(ts), max(ts) FROM tx WHERE process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE)""").fetchdf())
print(con.execute("""SELECT hour(ts) h, count(*) n, avg((process_date<ts::DATE)::INT) share_after FROM tx GROUP BY 1 ORDER BY 1""").fetchdf().to_string(index=False))
print(con.execute("""SELECT min(date_diff('second', process_date::TIMESTAMP, ts))/3600.0 min_h,
                             max(date_diff('second', process_date::TIMESTAMP, ts))/3600.0 max_h FROM tx""").fetchdf())
for t in ['cc','cp']:
    print(t, con.execute(f"""SELECT min(date_diff('second', process_date::TIMESTAMP, ts))/3600.0 min_h,
                             max(date_diff('second', process_date::TIMESTAMP, ts))/3600.0 max_h, min(ts), max(ts) FROM {t}""").fetchdf().to_string(index=False))
print("sv:", con.execute("""SELECT min(date_diff('hour', process_date::TIMESTAMP, ts)) min_h, max(date_diff('hour', process_date::TIMESTAMP, ts)) max_h,
   quantile_cont(date_diff('hour', process_date::TIMESTAMP, ts), [0.05,0.25,0.5,0.75,0.95]) q FROM sv""").fetchdf().to_string(index=False))
