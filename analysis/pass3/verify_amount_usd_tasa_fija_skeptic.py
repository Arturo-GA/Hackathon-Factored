import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
import pandas as pd
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30)

print("== 1. nulos por moneda ==")
print(q("""select currency, count(*) n, count(amount_usd) nn, 1-count(amount_usd)/count(*) null_rate,
  sum(case when amount_usd is not null and abs(amount_usd-amount)<0.01 then 1 else 0 end) eq_amount
  from tx group by 1 order by 1"""))

print("== 2. K por moneda y por trimestre (mediana, sd, min, max del cociente) ==")
print(q("""select currency, date_trunc('quarter', ts) qtr, count(*) n,
  median(amount/amount_usd) med, stddev(amount/amount_usd) sd,
  quantile_cont(amount/amount_usd, 0.001) p001, quantile_cont(amount/amount_usd, 0.999) p999
  from tx where amount_usd is not null and amount_usd>=1 group by 1,2 order by 1,2"""))

print("== 3. igualdad exacta con round(amount/K,2) ==")
print(q("""select currency, count(*) n,
  avg(case when amount_usd = round(amount/(case currency when 'ARS' then 350 when 'COP' then 4000 end),2) then 1.0 else 0 end) exact,
  max(abs(amount_usd - amount/(case currency when 'ARS' then 350 when 'COP' then 4000 end))) maxdiff,
  avg(case when abs(amount_usd - amount/(case currency when 'ARS' then 350 when 'COP' then 4000 end))<=0.0051 then 1.0 else 0 end) within_5m
  from tx where amount_usd is not null and currency in ('ARS','COP') group by 1"""))

print("== 4. tabla fx: niveles de USD->ARS / USD->COP ==")
print(q("""select src, dst, count(*) n, min(date) d0, max(date) d1, min(rate) mn, median(rate) med, max(rate) mx, stddev(rate) sd
  from fx where (src='USD' and dst in ('ARS','COP','MXN')) or (dst='USD' and src in ('ARS','COP','MXN')) group by 1,2 order by 1,2"""))
print(q("""select src,dst, date_trunc('year',date) y, median(rate) med from fx where src='USD' and dst in ('ARS','COP') group by all order by all"""))
