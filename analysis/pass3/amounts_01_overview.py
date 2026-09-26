import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
# currency x country
q("select currency, country, count(*) n, avg((amount_usd is null)::int) usd_null from tx group by all order by 1,2")
# amount_usd null by currency, ttype
q("select currency, ttype, count(*) n, avg((amount_usd is null)::int) usd_null from tx group by all order by 1,2")
# null by status/channel
q("select status, count(*) n, avg((amount_usd is null)::int) usd_null from tx group by all")
q("select channel, count(*) n, avg((amount_usd is null)::int) usd_null from tx group by all")
q("select year(ts) y, quarter(ts) qq, count(*) n, avg((amount_usd is null)::int) usd_null from tx group by all order by 1,2")
# amount stats per currency
q("""select currency, count(*) n, min(amount) mn, quantile_cont(amount,0.01) p01, quantile_cont(amount,0.25) p25, median(amount) med,
 quantile_cont(amount,0.75) p75, quantile_cont(amount,0.99) p99, max(amount) mx, avg((amount<0)::int) neg, avg((amount=0)::int) zero from tx group by all""")
