# H4: eventos digitales preceden en minutos a tx del mismo cliente? (ASOF join vs placebo desplazado)
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("select setseed(0.42)")
con.execute("create temp table cs_ as select customer_id from cu where hash(customer_id) % 10 = 0")  # ~10% clientes
con.execute("""create temp table dev as select customer_id, ts, (event_category='Transaction') is_tx, (event_type='Purchase') is_pur from de
  where customer_id in (select customer_id from cs_)""")
con.execute("""create temp table t as select customer_id, ts, ttype, channel,
   ts + to_days(cast(1+floor(random()*5) as int)) + to_minutes(cast(floor(random()*1440) as bigint)) as ts_pl
   from tx where customer_id in (select customer_id from cs_)""")
print(q("select (select count(*) from dev) nev, (select count(*) from t) ntx"))
for label, col in [('real','ts'),('placebo','ts_pl')]:
    con.execute(f"""create or replace temp table j as
      select t.channel, t.ttype, date_diff('minute', d.ts, t.{col}) dm, d.is_tx, d.is_pur
      from t asof left join dev d on t.customer_id=d.customer_id and d.ts <= t.{col}""")
    print(label)
    print(q("""select channel, count(*) n, avg((dm<=10)::int) p10m, avg((dm<=60)::int) p1h, avg((dm<=1440)::int) p1d,
       median(dm) med from j group by 1 order by 1"""))
con.execute("""create or replace temp table j2 as select t.channel, date_diff('minute', t.ts, d.ts) dm
   from t asof left join dev d on t.customer_id=d.customer_id and d.ts >= t.ts""")
print("after real"); print(q("select channel, avg((dm<=60)::int) p1h, median(dm) med from j2 group by 1 order by 1"))
