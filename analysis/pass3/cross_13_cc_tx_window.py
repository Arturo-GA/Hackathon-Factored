# H9: tx del cliente alrededor del contacto (mismo dia, -3d, -30d) por categoria; contacto real vs placebo
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("select setseed(0.1)")
con.execute("""create temp table c as select interaction_id, customer_id, ts, cat,
   ts - to_days(cast(10+floor(random()*40) as int)) ts_pl from cc where hash(customer_id)%5=0""")
con.execute("""create temp table t as select customer_id, ts, status, fraud, ttype, amount_usd, code from tx where customer_id in (select distinct customer_id from c)""")
print(q("select (select count(*) from c) nc, (select count(*) from t) nt"))
for col in ['ts','ts_pl']:
    con.execute(f"""create or replace temp table f as select c.interaction_id, c.cat,
      count(t.ts) filter (where t.ts between c.{col} - interval 1 day and c.{col}) n1,
      count(t.ts) filter (where t.ts between c.{col} - interval 3 day and c.{col}) n3,
      count(t.ts) filter (where t.ts between c.{col} - interval 3 day and c.{col} and t.status='Declined') d3,
      count(t.ts) filter (where t.ts between c.{col} - interval 30 day and c.{col} and t.fraud) f30,
      count(t.ts) filter (where t.ts between c.{col} - interval 30 day and c.{col}) n30,
      count(t.ts) filter (where t.ts between c.{col} and c.{col} + interval 3 day) a3
      from c left join t on t.customer_id=c.customer_id and t.ts between c.{col} - interval 30 day and c.{col} + interval 3 day
      group by 1,2""")
    print(col)
    print(q("""select cat, count(*) n, round(avg(n1),3) n1, round(avg(n3),3) n3, round(avg((d3>0)::int),4) anydecl3, round(avg((f30>0)::int),4) anyfraud30,
       round(avg(n30),2) n30, round(avg(a3),3) after3 from f group by rollup(cat) order by 1"""))
