import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
# ratio amount/amount_usd
q("""select currency, count(*) n, min(amount/amount_usd) mn, quantile_cont(amount/amount_usd,0.001) p001, median(amount/amount_usd) med,
 quantile_cont(amount/amount_usd,0.999) p999, max(amount/amount_usd) mx, stddev(amount/amount_usd) sd,
 count(distinct round(amount/amount_usd,2)) nd
 from tx where amount_usd is not null group by all""")
# ratio distribution top values
q("""select currency, round(amount/amount_usd,1) r, count(*) n from tx where amount_usd is not null group by all order by n desc limit 12""")
# fx range over time
q("""select src,dst, min(rate) mn, median(rate) med, max(rate) mx, min(date), max(date), count(*) from fx where 'USD' in (src,dst) group by all order by 1,2""")
# fx by year
q("""select src,dst, year(date) y, avg(rate) r from fx where (src='USD' and dst in ('ARS','COP','MXN')) group by all order by 1,2,3""")
# compare ratio with fx rate of the day
q("""with t as (select currency, cast(ts as date) d, process_date pd, amount, amount_usd, amount/amount_usd r from tx where amount_usd is not null)
select t.currency, count(*) n, corr(t.r, f.rate) corr_rate, median(abs(t.r/f.rate-1)) med_relerr_rate, avg((abs(t.r/f.rate-1)<0.001)::int) match_rate01,
 avg((abs(t.r/f.buy-1)<0.001)::int) match_buy, avg((abs(t.r/f.sell-1)<0.001)::int) match_sell
from t join fx f on f.date=t.d and f.src='USD' and f.dst=t.currency group by all""")
