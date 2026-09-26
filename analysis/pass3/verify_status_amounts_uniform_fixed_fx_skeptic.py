import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchall()
print("== currency x amount_usd null ==")
for r in q("""select currency, count(*), sum(amount_usd is null)::bigint, round(avg((amount_usd is null)::int),4) from tx group by 1 order by 1"""): print(r)
print("== currency x country ==")
for r in q("""select country, currency, count(*) from tx group by 1,2 order by 1,2"""): print(r)
print("== fixed-rate match (cent tolerance) ==")
for r in q("""select currency, count(*) n,
  sum(abs(amount_usd - round(amount/case currency when 'COP' then 4000 when 'ARS' then 350 end,2))<=0.005)::bigint exact_round,
  sum(abs(amount_usd - amount/case currency when 'COP' then 4000 when 'ARS' then 350 end)<=0.01)::bigint within_cent,
  max(abs(amount_usd - amount/case currency when 'COP' then 4000 when 'ARS' then 350 end)) maxdiff,
  min(amount/amount_usd), max(amount/amount_usd)
  from tx where amount_usd is not null and currency in ('COP','ARS') group by 1"""): print(r)
print("== any amount_usd in USD rows? ==", q("select count(*) from tx where currency='USD' and amount_usd is not null"))
print("== null in COP/ARS random? by ttype/status/year ==")
for r in q("""select currency, ttype, round(avg((amount_usd is null)::int),4), count(*) from tx where currency<>'USD' group by 1,2 order by 1,2"""): print(r)
for r in q("""select currency, status, round(avg((amount_usd is null)::int),4), count(*) from tx where currency<>'USD' group by 1,2 order by 1,2"""): print(r)
for r in q("""select currency, year(ts), round(avg((amount_usd is null)::int),4), count(*) from tx where currency<>'USD' group by 1,2 order by 1,2"""): print(r)
print("== daily fx match ==")
print(q("select src,dst,count(*),min(rate),avg(rate),max(rate) from fx where src='USD' and dst in ('COP','ARS') or dst='USD' and src in ('COP','ARS') group by 1,2"))
for r in q("""with t as (select currency, amount, amount_usd, cast(ts as date) d from tx where amount_usd is not null and currency in ('COP','ARS'))
 select t.currency, count(*), count(f.rate),
   sum(abs(t.amount_usd - round(t.amount/f.rate,2))<=0.01)::bigint,
   round(avg(t.amount/t.amount_usd),3), round(avg(f.rate),3), corr(t.amount/t.amount_usd, f.rate)
 from t left join fx f on f.date=t.d and f.src='USD' and f.dst=t.currency group by 1"""): print(r)
print("== min/max/mean by currency x ttype ==")
for r in q("""select currency, ttype, count(*), min(amount), max(amount), round(avg(amount),2), round(stddev(amount),2), sum(amount<=0)::bigint from tx group by 1,2 order by 1,2"""): print(r)
