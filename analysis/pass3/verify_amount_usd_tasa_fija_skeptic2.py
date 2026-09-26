import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
import pandas as pd
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30)

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
