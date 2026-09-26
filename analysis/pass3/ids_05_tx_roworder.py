# ids_05: ¿el orden de filas dentro de cada archivo diario de transacciones codifica algo? (ts, cliente, fraude, estado)
# Usa 1 de cada 5 archivos diarios (~220 días, ~890k filas) para caber en memoria.
import duckdb
con = duckdb.connect()
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=true")
q = lambda s: con.execute(s).fetchdf().to_string()
B='data/bronze'
con.execute(f"""create temp table t as select _source_file sf, file_row_number frn, customer_id cid, product_id pid,
   try_cast(transaction_date as timestamp) ts, try_cast(process_date as date) pd, transaction_status st, is_fraud='True' fraud,
   transaction_type tt, try_cast(fraud_score as double) fs
   from read_parquet('{B}/transactions.parquet', file_row_number=true)
   where hash(_source_file) % 5 = 0""")
con.execute("""create temp table t2 as select *, frn - min(frn) over (partition by sf) rin, count(*) over (partition by sf) nf,
   lag(ts) over (partition by sf order by frn) pts, lag(cid) over (partition by sf order by frn) pcid, lag(pid) over (partition by sf order by frn) ppid,
   lag(tt) over (partition by sf order by frn) ptt, lag(st) over (partition by sf order by frn) pst from t""")
con.execute("drop table t")
print(q("select count(*) n, count(distinct sf) nfiles, avg((ts>=pts)::int) ts_nondecreasing, avg((cid=pcid)::int) same_cust_prev, avg((pid=ppid)::int) same_prod_prev, avg((tt=ptt)::int) same_type_prev, avg((st=pst)::int) same_status_prev from t2 where pts is not null"))
print(q("select avg((ts::date = pd)::int) ts_eq_pd, avg((ts::date < pd)::int) ts_before_pd from t2"))
print(q("""select least(9, floor(rin*10.0/nf))::int pos_dec, count(*) n, avg(fraud::int)*1000 fraud_per_mil, avg((st='Declined')::int) decl,
   avg((st='Pending')::int) pend, avg((st='Reversed')::int) rev, avg(fs) fs, avg(hour(ts)) hr
   from t2 group by 1 order by 1"""))
print(q("select corr(rin*1.0/nf, epoch(ts)-epoch(pd::timestamp)) corr_pos_time, corr(rin*1.0/nf, epoch(ts)) corr_pos_ts from t2"))
print(q("select (rin=nf-1) is_last, (rin=0) is_first, count(*) n, avg(fraud::int) fraud, avg((st='Declined')::int) decl from t2 group by all"))
