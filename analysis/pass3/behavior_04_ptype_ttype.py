"""ptype x ttype (reglas deterministas?), tx fuera de vida del producto, last_tx vs opened/last_updated."""
from behavior_common import connect, q
con = connect()
ct = q(con, "SELECT p.ptype, t.ttype, count(*) n FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2")
pv = ct.pivot(index='ptype', columns='ttype', values='n').fillna(0).astype(int)
print(pv); print((pv.div(pv.sum(1), axis=0)*100).round(1))
ct2 = q(con, "SELECT p.ptype, coalesce(t.tcat,'NULL') tcat, count(*) n FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2")
print(ct2.pivot(index='ptype', columns='tcat', values='n').fillna(0).astype(int))
# per-tx fraction before opened / after expires / after last_updated / after closing
print(q(con, """SELECT count(*) n, avg((t.ts::DATE < p.opened)::INT) before_open, avg((t.ts::DATE > p.expires)::INT) after_exp,
    avg((t.ts > p.last_tx)::INT) after_lasttx FROM tx t JOIN pr p USING(product_id)"""))
print(q(con, """SELECT year(p.opened) y, count(*) n, avg((t.ts::DATE < p.opened)::INT) before_open FROM tx t JOIN pr p USING(product_id) GROUP BY 1 ORDER BY 1"""))
# last_tx relativo a opened y last_updated
print(q(con, """SELECT avg((last_tx::DATE>=opened)::INT) ge_open, avg((last_tx<=last_updated)::INT) le_upd, quantile_cont(date_diff('day', opened, last_tx::DATE),[0,0.01,0.5,0.99,1]) d_open,
   quantile_cont(date_diff('day', last_tx::DATE, DATE '2026-06-17'),[0,0.01,0.5,0.99,1]) d_end, min(last_updated), max(last_updated) FROM pr WHERE last_tx IS NOT NULL"""))
print(q(con, "SELECT pstatus, count(*) n, avg((last_tx IS NULL)::INT) null_lt, median(date_diff('day', last_tx::DATE, DATE '2026-06-17')) med_days_since FROM pr GROUP BY 1"))
