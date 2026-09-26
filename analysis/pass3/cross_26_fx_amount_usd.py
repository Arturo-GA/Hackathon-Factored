# H20: tx.amount_usd vs amount x fx (fecha de ts / process_date; rate/buy/sell); nulos de amount_usd
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("select currency, count(*) n, avg((amount_usd is null)::int) pnull, round(median(amount_usd/amount),6) med_ratio from tx group by 1"))
con.execute("create temp table s as select * from tx where amount_usd is not null and currency<>'USD' using sample 100000")
print(q("select count(*) from s"))
for dcol in ['cast(s.ts as date)','s.process_date']:
    for rcol in ['rate','buy','sell']:
        print(dcol, rcol, q(f"""select s.currency, count(*) n, count(f.rate) nfx,
           round(median(s.amount_usd/(s.amount*f.{rcol})),5) med_ratio,
           avg((abs(s.amount_usd - s.amount*f.{rcol}) <= 0.01 + 0.0001*s.amount_usd)::int) exact
           from s left join fx f on f.date={dcol} and f.src=s.currency and f.dst='USD' group by 1"""))
# ratio variation over time
print(q("""select s.currency, year(s.ts) y, round(median(s.amount_usd/s.amount),7) r, round(stddev(s.amount_usd/s.amount)/avg(s.amount_usd/s.amount),4) cv from s group by 1,2 order by 1,2"""))
print(q("select src, dst, year(date) y, round(avg(rate),6) r, round(stddev(rate)/avg(rate),4) cv from fx where dst='USD' group by 1,2,3 order by 1,3"))
# for USD: amount_usd = amount?
print(q("select avg((abs(amount_usd-amount)<0.005)::int) eq from tx where currency='USD' and amount_usd is not null"))
