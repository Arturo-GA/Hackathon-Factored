"""Verificación independiente: temporal_amounts_stationary_fx."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

print("== 0. amount <=0 / nulos por moneda")
print(q("""SELECT currency, count(*) n, sum((amount<=0)::INT) nonpos, sum((amount IS NULL)::INT) nnull,
   sum((amount_usd IS NULL)::INT) usd_null, avg((amount_usd IS NULL)::INT) usd_null_rate FROM tx GROUP BY 1 ORDER BY 1""").to_string(index=False))

print("\n== 1. pendiente ln(amount) vs tiempo (años), por moneda x ttype; usando ts y process_date")
s = q("""SELECT currency, ttype, count(*) n,
   regr_slope(ln(amount), epoch(ts)/31557600.0) slope_ts, regr_r2(ln(amount), epoch(ts)/31557600.0) r2_ts,
   regr_slope(ln(amount), (process_date - DATE '2023-06-17')/365.25) slope_pd, regr_r2(ln(amount), (process_date - DATE '2023-06-17')/365.25) r2_pd
   FROM tx WHERE amount>0 GROUP BY ALL ORDER BY 1,2""")
print(s.to_string(index=False))
print("max|slope_pd|=", s.slope_pd.abs().max(), " max r2_pd=", s.r2_pd.max())

print("\n== 2. mediana trimestral por moneda x ttype (rango min-max entre trimestres completos)")
m = q("""SELECT currency, ttype, date_trunc('quarter', process_date) qt, count(*) n, median(amount) med
   FROM tx WHERE amount>0 GROUP BY ALL""")
m = m[(m.qt > pd.Timestamp('2023-06-30')) & (m.qt < pd.Timestamp('2026-04-01'))]  # trimestres completos
g = m.groupby(['currency','ttype']).agg(nq=('med','size'), med_min=('med','min'), med_max=('med','max'), nmin=('n','min'))
g['rel_range'] = g.med_max/g.med_min - 1
print(g.round(3).to_string())
print("trimestres parciales incluidos:")
m2 = q("""SELECT currency, date_trunc('quarter', process_date) qt, count(*) n, median(amount) med FROM tx WHERE ttype='Purchase' GROUP BY ALL ORDER BY 1,2""")
print(m2.groupby('currency').med.agg(['min','max']).to_string())

print("\n== 3. fx en el tiempo")
f = q("""SELECT src, dst, date_trunc('quarter', date) qt, avg(rate) r, min(rate) mn, max(rate) mx, stddev(rate) sd, count(*) n
   FROM fx WHERE src='USD' GROUP BY ALL ORDER BY 1,2,3""")
print(f.groupby('dst').agg(qmean_min=('r','min'), qmean_max=('r','max'), daily_min=('mn','min'), daily_max=('mx','max'), sd_within_q=('sd','mean')).round(3).to_string())
print(q("""SELECT dst, regr_slope(ln(rate), (date - DATE '2023-06-17')/365.25) slope_log_yr, regr_r2(ln(rate), (date - DATE '2023-06-17')/365.25) r2,
   avg(rate) mean, stddev(rate)/avg(rate) cv, count(*) n, min(date) d0, max(date) d1 FROM fx WHERE src='USD' GROUP BY 1 ORDER BY 1""").to_string(index=False))
print("pares y conteos:")
print(q("SELECT src, dst, count(*) n, avg(rate) r FROM fx GROUP BY ALL ORDER BY 1,2").to_string(index=False))

print("\n== 4. ratio amount_usd/amount vs 1/350 y 1/4000 (todas las filas no nulas)")
r = q("""SELECT currency, count(*) n, avg(amount_usd/amount) ratio, stddev(amount_usd/amount) sd,
   min(amount_usd/amount) mn, max(amount_usd/amount) mx,
   avg(abs(amount_usd - amount/CASE currency WHEN 'ARS' THEN 350 WHEN 'COP' THEN 4000 END)/amount_usd) mape_fixed,
   max(abs(amount_usd - amount/CASE currency WHEN 'ARS' THEN 350 WHEN 'COP' THEN 4000 END)/amount_usd) maxape_fixed,
   max(abs(amount_usd - round(amount/CASE currency WHEN 'ARS' THEN 350 WHEN 'COP' THEN 4000 END, 2))) max_abs_diff_round2,
   avg((amount_usd = round(amount/CASE currency WHEN 'ARS' THEN 350 WHEN 'COP' THEN 4000 END, 2))::INT) exact_round2
   FROM tx WHERE amount_usd IS NOT NULL AND amount>0 GROUP BY 1""")
print(r.to_string(index=False))
print("1/350=", 1/350, " 1/4000=", 1/4000)

print("\n== 5. amount_usd vs amount/fx(dia) (process_date y date(ts)), todas las filas no nulas")
print(q("""WITH f AS (SELECT date, dst, rate FROM fx WHERE src='USD')
   SELECT t.currency, count(*) n,
     avg(abs(t.amount_usd - t.amount/f1.rate)/t.amount_usd) mape_fx_pd,
     avg(abs(t.amount_usd - t.amount/f2.rate)/t.amount_usd) mape_fx_ts,
     max(abs(t.amount_usd - t.amount/f1.rate)/t.amount_usd) maxape_pd
   FROM tx t JOIN f f1 ON f1.date=t.process_date AND f1.dst=t.currency
             LEFT JOIN f f2 ON f2.date=CAST(t.ts AS DATE) AND f2.dst=t.currency
   WHERE t.amount_usd IS NOT NULL AND t.amount>0 GROUP BY 1""").to_string(index=False))
print("desviación de fx diaria respecto a la constante:")
print(q("""SELECT dst, avg(abs(rate/CASE dst WHEN 'ARS' THEN 350 WHEN 'COP' THEN 4000 WHEN 'MXN' THEN 17 END - 1)) mean_abs_dev
   FROM fx WHERE src='USD' AND dst IN ('ARS','COP') GROUP BY 1""").to_string(index=False))

print("\n== 6. amount_usd nulo por año / ttype / status (ARS,COP)")
print(q("""SELECT currency, year(process_date) y, avg((amount_usd IS NULL)::INT) nr FROM tx GROUP BY ALL ORDER BY 1,2""").pivot(index='currency', columns='y', values='nr').round(4).to_string())
print(q("""SELECT ttype, avg((amount_usd IS NULL)::INT) nr, count(*) n FROM tx WHERE currency<>'USD' GROUP BY 1 ORDER BY 1""").round(4).to_string(index=False))
print(q("""SELECT status, avg((amount_usd IS NULL)::INT) nr, count(*) n FROM tx WHERE currency<>'USD' GROUP BY 1 ORDER BY 1""").round(4).to_string(index=False))

print("\n== 7. mediana en USD equivalente (tasas fijas) por moneda x ttype")
e = q("""SELECT currency, ttype, median(amount/CASE currency WHEN 'ARS' THEN 350 WHEN 'COP' THEN 4000 ELSE 1 END) med_usd_eq,
   quantile_cont(amount/CASE currency WHEN 'ARS' THEN 350 WHEN 'COP' THEN 4000 ELSE 1 END, 0.9) p90
   FROM tx WHERE amount>0 GROUP BY ALL""")
print(e.pivot(index='ttype', columns='currency', values='med_usd_eq').round(1).to_string())
print(e.pivot(index='ttype', columns='currency', values='p90').round(1).to_string())
print("\nmediana global Purchase por moneda (USD eq):")
print(q("""SELECT currency, median(amount/CASE currency WHEN 'ARS' THEN 350 WHEN 'COP' THEN 4000 ELSE 1 END) m FROM tx WHERE ttype='Purchase' GROUP BY 1""").to_string(index=False))
print("\nmoneda por país (share):")
print(q("""SELECT country, currency, count(*) n FROM tx GROUP BY ALL ORDER BY 1,2""").to_string(index=False))
