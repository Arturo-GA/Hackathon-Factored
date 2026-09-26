import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
con.execute("create temp table s as select currency, ts::date d, process_date pd, amount, amount_usd from tx where amount_usd is not null using sample 300000 rows")
for datecol in ['d','pd','d - 1','d + 1']:
    q(f"""select '{datecol}' fecha, s.currency,
     median(abs(s.amount/f.rate/s.amount_usd-1)) err_usd2x_rate, median(abs(s.amount/f.buy/s.amount_usd-1)) err_buy, median(abs(s.amount/f.sell/s.amount_usd-1)) err_sell,
     median(abs(s.amount*g.rate/s.amount_usd-1)) err_x2usd_rate, median(abs(s.amount*g.buy/s.amount_usd-1)) err_x2usd_buy, median(abs(s.amount*g.sell/s.amount_usd-1)) err_x2usd_sell,
     avg((abs(s.amount*g.rate/s.amount_usd-1)<0.0005)::int) hit_x2usd,
     median(abs(s.amount/(case s.currency when 'ARS' then 350 else 4000 end)/s.amount_usd-1)) err_fixed
     from s join fx f on f.date={('s.'+datecol) if datecol in ('d','pd') else 's.'+datecol} and f.src='USD' and f.dst=s.currency
     join fx g on g.date=f.date and g.src=s.currency and g.dst='USD' group by all""")
