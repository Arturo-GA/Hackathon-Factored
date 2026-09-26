# H13: coincidencias exactas de timestamp/fecha entre tx y otras tablas del mismo cliente (vs placebo cliente desplazado)
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("select min(ts), max(ts), avg((second(ts)=0)::int) sec0, avg((microsecond(ts)%1000000=0)::int) nomicro from (select ts from tx using sample 100000)"))
print(q("select min(ts), max(ts), avg((second(ts)=0)::int) sec0 from (select ts from cc using sample 100000)"))
con.execute("create temp table txs as select customer_id, ts, cast(ts as date) d, date_trunc('minute', ts) m from tx")
for name, tbl in [('cc','cc'),('cp','cp'),('cs','cs')]:
    print('==', name)
    print(q(f"""select count(*) n,
      avg((exists(select 1 from txs t where t.customer_id=x.customer_id and t.ts=x.ts))::int) same_ts,
      avg((exists(select 1 from txs t where t.customer_id=x.customer_id and t.m=date_trunc('minute',x.ts)))::int) same_min,
      avg((exists(select 1 from txs t where t.customer_id=x.customer_id and t.d=cast(x.ts as date)))::int) same_day,
      avg((exists(select 1 from txs t where t.customer_id=x.customer_id and t.d=cast(x.ts as date)+7))::int) placebo_day7
      from (select * from {tbl} using sample 20000) x"""))
# digital: same session-level day
print('== de')
print(q("""select count(*) n,
      avg((exists(select 1 from txs t where t.customer_id=x.customer_id and t.ts=x.ts))::int) same_ts,
      avg((exists(select 1 from txs t where t.customer_id=x.customer_id and t.m=date_trunc('minute',x.ts)))::int) same_min,
      avg((exists(select 1 from txs t where t.customer_id=x.customer_id and t.d=cast(x.ts as date)))::int) same_day,
      avg((exists(select 1 from txs t where t.customer_id=x.customer_id and t.d=cast(x.ts as date)+7))::int) placebo_day7
      from (select * from de where customer_id is not null and event_type in ('Purchase','FormSubmit') using sample 20000) x"""))
