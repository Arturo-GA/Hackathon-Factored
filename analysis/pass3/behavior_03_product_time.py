"""Tx vs fechas del producto: opened/expires/last_tx; ptype x ttype; saldo."""
from behavior_common import connect, q
con = connect()
con.execute("""CREATE TEMP TABLE pagg AS SELECT product_id, count(*) n, min(ts) first_ts, max(ts) last_ts,
   sum(CASE WHEN ttype='Deposit' THEN amount ELSE 0 END) dep, sum(CASE WHEN ttype IN ('Withdrawal','Purchase','Payment','Transfer') THEN amount ELSE 0 END) outf,
   sum(CASE WHEN status='Approved' AND ttype='Deposit' THEN amount ELSE 0 END) dep_ok,
   sum(CASE WHEN status='Approved' AND ttype IN ('Withdrawal','Purchase','Payment','Transfer') THEN amount ELSE 0 END) out_ok
   FROM tx GROUP BY 1""")
print(q(con, """SELECT p.ptype, count(*) n,
  avg((a.first_ts < p.opened)::INT) pct_tx_before_open,
  avg((a.last_ts > p.expires)::INT) pct_tx_after_exp,
  avg((p.last_tx IS NULL)::INT) lt_null,
  avg((abs(epoch(p.last_tx)-epoch(a.last_ts))<86400)::INT) lt_match_1d,
  avg((p.last_tx > a.last_ts)::INT) lt_after, avg((p.last_tx < a.last_ts)::INT) lt_before
  FROM pr p JOIN pagg a USING(product_id) GROUP BY 1 ORDER BY 2 DESC"""))
print(q(con, "SELECT min(opened), max(opened), min(expires), max(expires), min(last_tx), max(last_tx) FROM pr"))
print(q(con, """SELECT quantile_cont(date_diff('day', p.last_tx, a.last_ts),[0.01,0.1,0.5,0.9,0.99]) q FROM pr p JOIN pagg a USING(product_id)"""))
print(q(con, """SELECT quantile_cont(date_diff('day', p.opened, a.first_ts),[0.01,0.1,0.5,0.9,0.99]) q, avg((date_diff('day', p.opened, a.first_ts)<0)::INT) FROM pr p JOIN pagg a USING(product_id)"""))
# last_tx relación con last_updated u otros
print(q(con, """SELECT avg((p.last_tx<=p.last_updated)::INT) lt_le_upd, corr(epoch(p.last_tx), epoch(a.last_ts)) c_last, corr(epoch(p.last_tx), epoch(p.opened)) c_open, corr(epoch(p.last_tx), epoch(p.last_updated)) c_upd FROM pr p JOIN pagg a USING(product_id)"""))
# saldo
print(q(con, """SELECT p.ptype, p.currency, count(*) n, corr(p.bal, a.dep - a.outf) c_all, corr(p.bal, a.dep_ok-a.out_ok) c_ok, corr(p.bal, a.dep) c_dep,
  median(p.bal) med_bal, median(a.dep-a.outf) med_net FROM pr p JOIN pagg a USING(product_id) GROUP BY 1,2 ORDER BY 1,2"""))
