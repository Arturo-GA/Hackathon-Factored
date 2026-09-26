# H10: pr.last_tx vs max(tx.ts); pr.opened vs primera tx; tx despues de expires; tx antes de registro; bal vs suma tx
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("""create temp table agg as select product_id, count(*) n, min(ts) first_ts, max(ts) last_ts,
   sum(case when ttype in ('Deposit') then amount else 0 end) dep, sum(case when ttype in ('Purchase','Withdrawal','Transfer','Payment') then amount else 0 end) outf,
   sum(amount) tot
   from tx group by 1""")
print(q("select count(*) nprod_tx, (select count(*) from pr) npr, (select count(*) from pr where last_tx is not null) n_lasttx from agg"))
print(q("""select p.pstatus, count(*) n, count(a.product_id) with_tx, count(p.last_tx) with_lasttx,
   avg((a.product_id is not null)::int) p_has_tx,
   avg((cast(p.last_tx as date)=cast(a.last_ts as date))::int) lasttx_eq_day,
   median(date_diff('day', a.last_ts, p.last_tx)) med_diff_days,
   avg((a.first_ts < p.opened)::int) tx_before_open,
   avg((a.last_ts > p.expires)::int) tx_after_exp
   from pr p left join agg a using(product_id) group by rollup(p.pstatus)"""))
print(q("""select quantile_cont(date_diff('day', a.last_ts, p.last_tx),[0.01,0.1,0.5,0.9,0.99]) q from pr p join agg a using(product_id) where p.last_tx is not null"""))
print(q("""select corr(p.bal, a.tot) r_tot, corr(p.bal, a.dep-a.outf) r_net, corr(p.bal, a.n) r_n from pr p join agg a using(product_id) where p.bal is not null"""))
print(q("""select p.ptype, count(*) n, round(avg(a.n),1) avg_tx, round(corr(p.bal, a.n),3) r_bal_n, round(corr(p.credit_limit, a.tot),3) r_lim from pr p join agg a using(product_id) group by 1 order by 2 desc"""))
# tx before customer registration
print(q("""select count(*) n, avg((t.ts < c.registration_date)::int) before_reg, avg((cast(t.ts as date) < c.dob + interval 18 year)::int) minor
  from (select customer_id, ts from tx using sample 300000) t join cu c using(customer_id)"""))
# pr.opened vs cu.registration_date
print(q("select count(*) n, avg((p.opened < cast(c.registration_date as date))::int) opened_before_reg from pr p join cu c using(customer_id)"))
