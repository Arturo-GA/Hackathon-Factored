import duckdb, pandas as pd, warnings
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width',250); pd.set_option('display.max_colwidth',60)
print(q("""select currency, count(*) n, avg(case when abs(amount/(case currency when 'COP' then 4000 else 350 end) - amount_usd) <= 0.0051 then 1 else 0 end) fixed_ok
 from tx where amount_usd is not null group by 1""").to_string())
print(q("""select t.currency, count(*) n, avg(case when abs(t.amount/f.rate - t.amount_usd) <= 0.0051 then 1 else 0 end) fx_ok,
  corr(t.amount/t.amount_usd, f.rate) corr_rate
 from (select * from tx where amount_usd is not null using sample 200000 rows) t join fx f on f.date=cast(t.ts as date) and f.src='USD' and f.dst=t.currency group by 1""").to_string())
print("excepciones process_date:")
print(q("""select ts, process_date, country, status from tx where process_date <> cast(ts - interval 6 hour as date) limit 12""").to_string())
print(q("""select count(*) from tx where process_date <> cast(ts - interval 6 hour as date)""").to_string())
print(q("select case_type, category, count(*) n from cp group by 1,2 order by 3 desc limit 30").to_string())
print(q("select event_type, event_category, count(*) n, avg(case when product_id is null then 0 else 1 end) has_prod, avg(case when event_value is null then 0 else 1 end) has_val from de group by 1,2 order by 3 desc limit 40").to_string())
