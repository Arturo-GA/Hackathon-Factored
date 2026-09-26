import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: print(con.execute(s).df().to_string(), '\n')
K = "(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"
LO = "(case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Transfer' then 100 when 'Payment' then 50 when 'Deposit' then 50 else 10 end)"
HI = "(case ttype when 'Purchase' then 500 when 'Withdrawal' then 500 when 'Transfer' then 10000 when 'Payment' then 2000 when 'Deposit' then 5000 else 1000 end)"
con.execute(f"""create temp view v as select *, amount/{K} a, (amount/{K}-{LO})/({HI}-{LO}) u from tx""")

print("== G. repeated exact amounts within customer (recurring payments?) vs expectation ==")
# observed pairs with same (ttype,currency,amount) per customer; expected under uniform on cent grid
q("""with g as (select customer_id, ttype, currency, amount, count(*) c from tx group by all),
 obs as (select sum(c*(c-1)/2) pairs from g),
 cnt as (select customer_id, ttype, currency, count(*) n from tx group by all),
 ex as (select sum(n*(n-1)/2 / (({HI}-{LO})*{K}*100.0 + 1)) exp_pairs from cnt)
 select obs.pairs, ex.exp_pairs, obs.pairs/ex.exp_pairs ratio from obs, ex""".replace('{HI}', HI).replace('{LO}', LO).replace('{K}', K))

print("== H. decimals: amounts in local currency with 2 decimals, integers ==")
q("""select currency, round(avg((abs(amount*100-round(amount*100))<1e-6)::int),4) two_dec, round(avg((amount=floor(amount))::int),4) whole,
 round(avg((abs(a*100-round(a*100))<1e-6)::int),4) usd_eq_cents_exact from v group by 1""")

print("== I. decline rate by amount quintile within ttype (max RR) ==")
q("""select ttype, least(floor(u*5),4) qb, count(*) n, round(avg((status='Declined')::int)*100,2) decl_pct, round(avg((status='Reversed')::int)*100,2) rev_pct, round(avg((status='Pending')::int)*100,2) pend_pct
 from v group by all order by 1,2""")

print("== J. grid check: is local amount = USD cents * K ? ==")
q("""select currency, count(*) n, round(avg((abs(a*100-round(a*100))<1e-4)::int),4) usd_cent_grid, count(distinct amount) nd from v where currency<>'USD' group by 1""")
print("== K. same-amount pairs by customer, grouping USD-eq cents ==")
q("""with g as (select customer_id, ttype, round(a,2) ra, count(*) c from v group by all),
 obs as (select sum(c*(c-1)/2) pairs from g),
 cnt as (select customer_id, ttype, count(*) n from v group by all),
 ex as (select sum(n*(n-1)/2 / (({HI}-{LO})*100.0 + 1)) exp_pairs from cnt)
 select obs.pairs, ex.exp_pairs, obs.pairs/ex.exp_pairs ratio from obs, ex""".replace('{HI}', HI).replace('{LO}', LO))
