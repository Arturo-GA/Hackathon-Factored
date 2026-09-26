import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
con.execute("create temp table e as select event_id, customer_id, event_value v, ts from de where event_value is not null and customer_id is not null")
con.execute("""create temp table t as select customer_id, ts, amount,
   amount/(case currency when 'ARS' then 350.0 when 'COP' then 4000.0 else 1.0 end) usd from tx where customer_id in (select customer_id from e)""")
for shift in [0, 90, -90, 200]:
    r = con.execute(f"""select count(distinct e.event_id) from e join t on t.customer_id=e.customer_id
        and abs(epoch(t.ts)-epoch(e.ts + interval {shift} day))<86400 and abs(t.usd/e.v-1)<0.01""").fetchone()[0]
    print('shift', shift, 'match USD ±1d ±1%:', r)
