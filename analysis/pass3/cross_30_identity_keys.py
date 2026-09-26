# H24: llaves de identidad alternativas: de.session_id / de.ip_address -> cliente (imputar 24% anonimos?); duplicados de documento/email/telefono en cu
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("""create temp table s as select session_id, count(*) n, count(distinct customer_id) ncust, sum((customer_id is null)::int) nanon,
   count(distinct ip_address) nip, count(distinct platform) nplat, min(ts) t0, max(ts) t1 from de where hash(session_id)%10=0 group by 1""")
print(q("""select count(*) sessions, avg(n) ev_per_sess, avg((ncust>1)::int) multi_cust, avg((ncust=0)::int) all_anon,
   avg((ncust=1 and nanon>0)::int) mixed_imputable, avg(nip) avg_ip, avg(nplat) avg_plat, median(date_diff('minute', t0, t1)) med_span_min from s"""))
print(q("select ncust, count(*) from s group by 1 order by 1"))
con.execute("""create temp table ip as select ip_address, count(*) n, count(distinct customer_id) ncust, sum((customer_id is null)::int) nanon from de where hash(ip_address)%20=0 group by 1""")
print(q("""select count(*) ips, avg(n) ev, avg((ncust>1)::int) multi, quantile_cont(ncust,[0.5,0.9,0.99]) q, max(ncust) from ip"""))
print(q("""select count(*) n, count(distinct document_number) ndoc, count(distinct email) nem, count(distinct mobile_phone) nph,
   count(distinct first_name||last_name||cast(dob as varchar)) nident from cu"""))
print(q("""with d as (select document_number, count(*) k from cu group by 1 having count(*)>1) select count(*) dup_docs, sum(k) customers from d"""))
print(q("""with d as (select email, count(*) k from cu group by 1 having count(*)>1) select count(*) dup_email, sum(k) customers from d"""))
