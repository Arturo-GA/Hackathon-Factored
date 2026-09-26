"""Addendum escéptico de temporal_amounts_stationary_fx:
(a) ¿la mezcla de ttype/moneda cambia en el tiempo? (afectaría 'monto inusual sin ajustar por fecha' a nivel global)
(b) elasticidad monto~fx por ttype con SE (¿el 0,86 de ARS es ruido?)."""
import duckdb, numpy as np, pandas as pd
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
K = "(CASE currency WHEN 'ARS' THEN 350.0 WHEN 'COP' THEN 4000.0 ELSE 1.0 END)"

print("== a. mezcla de ttype y moneda por año (% de filas) y monto medio en USD-eq ==")
m = q(f"""SELECT year(process_date) yr, ttype, count(*) n FROM tx GROUP BY ALL""")
p = m.pivot(index='yr', columns='ttype', values='n'); print((100*p.div(p.sum(1), axis=0)).round(2).to_string())
c = q("""SELECT year(process_date) yr, currency, count(*) n FROM tx GROUP BY ALL""").pivot(index='yr', columns='currency', values='n')
print((100*c.div(c.sum(1), axis=0)).round(2).to_string())
print(q(f"""SELECT year(process_date) yr, avg(amount/{K}) mean_usd_eq, median(amount/{K}) med_usd_eq FROM tx GROUP BY 1 ORDER BY 1""").round(1).to_string(index=False))

print("\n== b. elasticidad ln(amount) ~ ln(fx_dia/K) por moneda x ttype (process_date) ==")
r = q("""WITH f AS (SELECT date, dst, rate FROM fx WHERE src='USD' AND dst IN ('ARS','COP')),
  t AS (SELECT tx.currency, tx.ttype, ln(tx.amount) y, ln(f.rate/(CASE f.dst WHEN 'ARS' THEN 350.0 ELSE 4000.0 END)) x
        FROM tx JOIN f ON f.date=tx.process_date AND f.dst=tx.currency WHERE tx.amount>0)
  SELECT currency, ttype, count(*) n, regr_slope(y,x) b, regr_r2(y,x) r2, var_samp(y) vy, var_samp(x) vx FROM t GROUP BY ALL ORDER BY 1,2""")
r['se'] = np.sqrt((1-r.r2)*r.vy/((r.n-2)*r.vx)); r['z_vs0'] = r.b/r.se; r['z_vs1'] = (r.b-1)/r.se
print(r[['currency','ttype','n','b','se','z_vs0','z_vs1']].round(3).to_string(index=False))
