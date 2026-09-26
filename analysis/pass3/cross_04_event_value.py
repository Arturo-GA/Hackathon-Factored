# H3: de.event_value (FormSubmit/Purchase) coincide con montos de tx del cliente? precede en minutos?
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("""select min(event_value), quantile_cont(event_value,[0.01,0.25,0.5,0.75,0.99]) qs, max(event_value),
  avg((event_value = round(event_value,2))::int) r2, avg((event_value=round(event_value))::int) r0 from de where event_value is not null"""))
print(q("""select min(amount), quantile_cont(amount,[0.01,0.25,0.5,0.75,0.99]) qs, max(amount), avg((amount=round(amount,2))::int) r2 from tx"""))
# events con valor y cliente
con.execute("""create temp table ev as select event_id, customer_id, ts, event_type, action, round(event_value,2) v
  from de where event_value is not null and customer_id is not null""")
print(q("select count(*) n, count(distinct customer_id) nc from ev"))
# exact amount match within same customer (any time)
con.execute("""create temp table txc as select customer_id, ts, round(amount,2) a, round(amount_usd,2) au, ttype, channel, status from tx
  where customer_id in (select distinct customer_id from ev)""")
print(q("select count(*) from txc"))
print(q("""select count(*) n_ev,
  count(*) filter (where exists (select 1 from txc t where t.customer_id=ev.customer_id and t.a=ev.v)) m_amt,
  count(*) filter (where exists (select 1 from txc t where t.customer_id=ev.customer_id and t.au=ev.v)) m_usd
  from (select * from ev using sample 20000) ev"""))
# baseline: match against random other customer's tx amounts? global exact-value match rate
print(q("""select count(*) n_ev, count(*) filter (where v in (select a from txc)) m_any from (select * from ev using sample 20000)"""))
