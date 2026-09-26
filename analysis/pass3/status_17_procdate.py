"""Regla exacta de process_date: DATE(ts - 6h - 1s) (corte contable a las 06:00:00 inclusive)."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
for t in ['tx','cc']:
    try:
        print(t, con.execute(f"""select count(*) n,
          sum(case when process_date = cast(ts - interval 6 hour - interval 1 second as date) then 1 else 0 end) ok_6h1s,
          sum(case when process_date = cast(ts - interval 6 hour as date) then 1 else 0 end) ok_6h,
          sum(case when process_date < cast(ts as date) then 1 else 0 end) fecha_anterior from {t}""").fetchall())
    except Exception as e: print(t, e)
print(con.execute("""select count(*) from tx where process_date <> cast(ts - interval 6 hour as date) and strftime(ts,'%H:%M:%S')<>'06:00:00'""").fetchall())
print(con.execute("""select hour(ts) h, date_diff('day', cast(ts as date), process_date) d, count(*) n from cc group by 1,2 order by 1,2""").fetchdf().pivot(index='h',columns='d',values='n').T.to_string())
