"""Verificador escéptico: temporal_amounts_stationary_fx"""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
print("== 0. signos de amount / nulos ==")
print(con.execute("""SELECT currency, count(*) n, sum((amount<=0)::INT) nonpos, sum((amount IS NULL)::INT) nnull,
  sum((amount_usd IS NULL)::INT) usd_null, min(amount) mn, max(amount) mx FROM tx GROUP BY 1""").fetchdf().to_string(index=False))
print("== 1. pendientes ln(amount) por año, por moneda x ttype (todas) ==")
s = con.execute("""SELECT currency, ttype, count(*) n,
   regr_slope(ln(amount), date_diff('day', DATE '2023-06-17', process_date)/365.25) slope,
   regr_r2(ln(amount), date_diff('day', DATE '2023-06-17', process_date)/365.25) r2
   FROM tx WHERE amount>0 GROUP BY ALL ORDER BY 1,2""").fetchdf()
print(s.round(5).to_string(index=False))
print("max |slope|:", s.slope.abs().max(), " max r2:", s.r2.max())
print("== 1b. pendientes con ts (no process_date) y en percentiles p10/p90/p99 por año ==")
print(con.execute("""SELECT currency, year(ts) y, count(*) n, quantile_cont(amount,0.1) p10, median(amount) p50,
  quantile_cont(amount,0.9) p90, quantile_cont(amount,0.99) p99 FROM tx WHERE ttype='Purchase' GROUP BY ALL ORDER BY 1,2""").fetchdf().round(1).to_string(index=False))
print("== 2. ratio amount_usd/amount vs 1/350, 1/4000; ¿round(amount/rate,2)? ==")
print(con.execute("""SELECT currency, count(*) n, avg(amount/amount_usd) implied, stddev(amount/amount_usd) sd_implied,
  avg(abs(amount_usd*350/amount-1)) FILTER (WHERE currency='ARS') relerr350,
  avg(abs(amount_usd*4000/amount-1)) FILTER (WHERE currency='COP') relerr4000,
  avg((amount_usd = round(amount/350,2))::INT) FILTER (WHERE currency='ARS') exact_round350,
  avg((abs(amount_usd - round(amount/350,2))<=0.011)::INT) FILTER (WHERE currency='ARS') near_round350,
  avg((amount_usd = round(amount/4000,2))::INT) FILTER (WHERE currency='COP') exact_round4000,
  avg((abs(amount_usd - round(amount/4000,2))<=0.011)::INT) FILTER (WHERE currency='COP') near_round4000,
  max(abs(amount_usd - amount/350)) FILTER (WHERE currency='ARS') maxabs350,
  max(abs(amount_usd - amount/4000)) FILTER (WHERE currency='COP') maxabs4000
  FROM tx WHERE amount_usd IS NOT NULL AND amount>0 GROUP BY 1""").fetchdf().T.to_string())
print("== 2b. ¿amount es round(usd*rate,2)? decimales de amount y amount_usd ==")
print(con.execute("""SELECT currency,
  avg((abs(amount*100 - round(amount*100))<1e-6)::INT) amount_2dec,
  avg((abs(amount_usd*100 - round(amount_usd*100))<1e-6)::INT) usd_2dec,
  avg((abs(amount - round(amount))<1e-9)::INT) amount_int
  FROM tx WHERE amount_usd IS NOT NULL GROUP BY 1""").fetchdf().to_string(index=False))
print("== 3. fx diario USD->X: tendencia y rango ==")
print(con.execute("""SELECT src,dst,count(*) n, min(date) d0, max(date) d1, avg(rate) m, stddev(rate) sd, min(rate) mn, max(rate) mx,
  regr_slope(rate, date_diff('day', DATE '2023-06-17', date)/365.25)/avg(rate) rel_slope_yr,
  regr_r2(rate, date_diff('day', DATE '2023-06-17', date)) r2
  FROM fx WHERE src='USD' GROUP BY ALL ORDER BY 2""").fetchdf().round(4).to_string(index=False))
print(con.execute("""SELECT dst, year(date) y, avg(rate) r FROM fx WHERE src='USD' GROUP BY ALL ORDER BY 1,2""").fetchdf().pivot(index='dst',columns='y',values='r').round(2))
# ¿fx diario es ruido iid alrededor de constante? autocorrelación lag1
print(con.execute("""WITH f AS (SELECT dst, date, rate, lag(rate) OVER (PARTITION BY dst ORDER BY date) pr FROM fx WHERE src='USD')
   SELECT dst, corr(rate, pr) ac1 FROM f GROUP BY 1""").fetchdf().round(3).to_string(index=False))
print("== 4. amount_usd vs amount/fx del día (process_date y date(ts)) ==")
print(con.execute("""WITH f AS (SELECT date, dst, rate FROM fx WHERE src='USD'),
  t AS (SELECT * FROM tx USING SAMPLE 300000 ROWS)
  SELECT t.currency, count(*) n,
   avg(abs(t.amount_usd - t.amount/f.rate)/t.amount_usd) mape_pd,
   avg(abs(t.amount_usd - t.amount/g.rate)/t.amount_usd) mape_ts
   FROM t JOIN f ON f.date=t.process_date AND f.dst=t.currency
          JOIN f g ON g.date=CAST(t.ts AS DATE) AND g.dst=t.currency
   WHERE t.amount_usd>0 GROUP BY 1""").fetchdf().round(5).to_string(index=False))
print("== 5. nulos amount_usd por moneda/status/ttype/canal ==")
print(con.execute("""SELECT currency, status, count(*) n, avg((amount_usd IS NULL)::INT) nul FROM tx GROUP BY ALL ORDER BY 1,2""").fetchdf().round(4).to_string(index=False))
print(con.execute("""SELECT ttype, avg((amount_usd IS NULL)::INT) nul, count(*) n FROM tx WHERE currency<>'USD' GROUP BY 1 ORDER BY 1""").fetchdf().round(4).to_string(index=False))
print(con.execute("""SELECT channel, avg((amount_usd IS NULL)::INT) nul, count(*) n FROM tx WHERE currency<>'USD' GROUP BY 1 ORDER BY 1""").fetchdf().round(4).to_string(index=False))
print("== 6. mediana en USD equivalente (350/4000) por ttype y moneda ==")
print(con.execute("""SELECT ttype, currency, count(*) n,
  median(CASE currency WHEN 'ARS' THEN amount/350 WHEN 'COP' THEN amount/4000 ELSE amount END) med_usd_eq,
  quantile_cont(CASE currency WHEN 'ARS' THEN amount/350 WHEN 'COP' THEN amount/4000 ELSE amount END, 0.9) p90_usd_eq
  FROM tx GROUP BY ALL ORDER BY 1,2""").fetchdf().pivot(index='ttype', columns='currency', values=['med_usd_eq','p90_usd_eq']).round(1).to_string())
print("== 7. moneda vs país (¿MXN ausente => México en USD?) ==")
print(con.execute("""SELECT country, currency, count(*) n FROM tx GROUP BY ALL ORDER BY 1,2""").fetchdf().to_string(index=False))
print("== 8. balances de productos por moneda (¿también escala 350/4000?) ==")
print(con.execute("""SELECT currency, ptype, count(*) n, median(bal) med_bal, median(credit_limit) med_lim FROM pr GROUP BY ALL ORDER BY 2,1""").fetchdf().round(1).to_string(index=False))
