"""H9: montos a lo largo del tiempo por moneda (¿inflación ARS?), y amount_usd vs fx del día.
H10: ¿amount_usd nulo depende del tiempo?"""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = con.execute("""SELECT currency, date_trunc('quarter', process_date) q, count(*) n, median(amount) med, avg(amount) mean,
   quantile_cont(amount, 0.9) p90, avg((amount_usd IS NULL)::INT) null_usd, median(amount_usd) med_usd,
   median(amount/amount_usd) FILTER (WHERE amount_usd>0) implied_rate
   FROM tx WHERE ttype='Purchase' GROUP BY ALL ORDER BY 1,2""").fetchdf()
print(q.round(3).to_string(index=False))
# pendiente log-monto por año por moneda y tipo
s = con.execute("""SELECT currency, ttype, regr_slope(ln(amount), date_diff('day', DATE '2023-06-17', process_date)/365.25) slope_log_per_year,
   regr_r2(ln(amount), date_diff('day', DATE '2023-06-17', process_date)/365.25) r2, count(*) n
   FROM tx WHERE amount>0 GROUP BY ALL ORDER BY 1,2""").fetchdf()
print(s.round(5).to_string(index=False))
# fx: tasa ARS por USD en el tiempo
print(con.execute("""SELECT src, dst, date_trunc('quarter', date) q, avg(rate) r FROM fx WHERE (src='USD' AND dst IN ('ARS','COP','MXN'))
   GROUP BY ALL ORDER BY 1,2,3""").fetchdf().pivot(index='q', columns='dst', values='r').round(2).to_string())
# amount_usd vs amount/fx(process_date)
print(con.execute("""WITH f AS (SELECT date, dst, rate FROM fx WHERE src='USD')
   SELECT t.currency, count(*) n, avg(abs(t.amount_usd - t.amount/f.rate)/t.amount_usd) mape_fx_pd,
   corr(t.amount_usd, t.amount/f.rate) corr_fx
   FROM (SELECT * FROM tx USING SAMPLE 300000 ROWS) t JOIN f ON f.date=t.process_date AND f.dst=t.currency
   WHERE t.amount_usd>0 GROUP BY 1""").fetchdf().round(4).to_string(index=False))
print(con.execute("""SELECT currency, avg(amount_usd/amount) ratio, stddev(amount_usd/amount) sd, min(amount_usd/amount) mn, max(amount_usd/amount) mx
   FROM tx WHERE amount>0 AND amount_usd IS NOT NULL GROUP BY 1""").fetchdf().to_string(index=False))
print(con.execute("""SELECT currency, year(process_date) y, avg((amount_usd IS NULL)::INT) null_usd FROM tx GROUP BY ALL ORDER BY 1,2""").fetchdf().pivot(index='currency', columns='y', values='null_usd').round(4))
