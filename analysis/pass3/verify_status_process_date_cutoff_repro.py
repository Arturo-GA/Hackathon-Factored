import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

def q(s):
    return con.execute(s).fetchall()

print("== TX: range of ts, process_date")
print(q("select min(ts), max(ts), min(process_date), max(process_date), count(*), count(process_date), count(ts) from tx"))

print("== TX: lag distribution (process_date - date(ts))")
print(q("select date_diff('day', cast(ts as date), process_date) d, count(*) from tx group by 1 order by 1"))

print("== TX: test offsets")
for h in [0, 4, 5, 6, 7, 8]:
    r = q(f"select sum(case when process_date = cast(ts - interval {h} hour as date) then 1 else 0 end), count(*) from tx")
    print(h, r, r[0][0]/r[0][1])

print("== TX: exceptions to DATE(ts-6h), by hour/min/sec")
print(q("""select hour(ts), minute(ts), second(ts), date_diff('day', cast(ts as date), process_date) d, count(*)
from tx where process_date <> cast(ts - interval 6 hour as date) group by all order by 5 desc limit 20"""))
print(q("select count(*) from tx where process_date <> cast(ts - interval 6 hour as date)"))
print("ts exactly 06:00:00 total:", q("select count(*), sum(case when process_date=cast(ts as date) then 1 else 0 end) from tx where hour(ts)=6 and minute(ts)=0 and second(ts)=0 and microsecond(ts)=0"))
print("ts with fractional seconds?:", q("select count(*) from tx where microsecond(ts)<>0"))

print("== TX: hour vs lag")
print(q("""select hour(ts) h, sum(case when process_date < cast(ts as date) then 1 else 0 end) prev, count(*) n
from tx group by 1 order by 1"""))
print("prev-day count:", q("select sum(case when process_date < cast(ts as date) then 1 else 0 end), count(*), avg(case when process_date < cast(ts as date) then 1.0 else 0 end) from tx"))
print("prev-day with hour>=6:", q("select count(*) from tx where process_date < cast(ts as date) and hour(ts)>=6"))

print("== TX: by country/status")
print(q("""select country, avg(case when process_date = cast(ts - interval 6 hour as date) then 1.0 else 0 end), count(*) from tx group by 1 order by 1"""))
print(q("""select status, avg(case when process_date = cast(ts - interval 6 hour as date) then 1.0 else 0 end), count(*) from tx group by 1 order by 1"""))

print("== CC")
print(q("select min(ts), max(ts), min(process_date), max(process_date), count(*), count(process_date) from cc"))
print(q("select date_diff('day', cast(ts as date), process_date) d, count(*) from cc group by 1 order by 1"))
for h in [0, 6, 7, 8, 9]:
    r = q(f"select sum(case when process_date = cast(ts - interval {h} hour as date) then 1 else 0 end), count(*) from cc")
    print(h, r, r[0][0]/r[0][1])
print(q("""select hour(ts) h, sum(case when process_date < cast(ts as date) then 1 else 0 end) prev, count(*) n from cc group by 1 order by 1"""))
print("cc exceptions to 8h:", q("""select hour(ts), minute(ts), second(ts), count(*) from cc where process_date <> cast(ts - interval 8 hour as date) group by all order by 4 desc limit 10"""))
print("cc ts exactly 08:00:00:", q("select count(*) from cc where hour(ts)=8 and minute(ts)=0 and second(ts)=0"))

print("== CC by channel/cat")
print(q("select channel, avg(case when process_date = cast(ts - interval 8 hour as date) then 1.0 else 0 end), count(*) from cc group by 1"))

print("== Weekday pattern: process_date vs DATE(ts) (which one is 'primary')")
for t in ['cc', 'tx']:
    print(t, q(f"""select dayofweek(process_date) dw, count(*) from {t} group by 1 order by 1"""))
    print(t, q(f"""select dayofweek(cast(ts as date)) dw, count(*) from {t} group by 1 order by 1"""))
print("exact-boundary 06:00:00 split:", q("""select date_diff('day', cast(ts as date), process_date), count(*) from tx where strftime(ts, '%H:%M:%S')='06:00:00' group by 1"""))
print("exact-boundary 08:00:00 cc split:", q("""select date_diff('day', cast(ts as date), process_date), count(*) from cc where strftime(ts, '%H:%M:%S')='08:00:00' group by 1"""))
