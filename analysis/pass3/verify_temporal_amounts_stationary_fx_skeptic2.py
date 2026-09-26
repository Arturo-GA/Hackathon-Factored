"""Verificación escéptica (2a ronda) de temporal_amounts_stationary_fx.
Ángulos nuevos: (a) z de las pendientes (¿algún tipo con tendencia real?), topes min/max por año,
(b) ¿el monto LOCAL depende del fx del día? (pendiente de ln(amount) sobre ln(fx/K); 0 = no, 1 = convertido con fx),
(c) ¿una tasa fx suavizada (media móvil 30d / media anual) reproduce amount_usd mejor que K fijo?,
(d) estacionalidad mensual / día de semana del monto normalizado, (e) inflación en saldos/límites de pr por año de apertura."""
import duckdb, numpy as np, pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
K = "(CASE currency WHEN 'ARS' THEN 350.0 WHEN 'COP' THEN 4000.0 ELSE 1.0 END)"

print("== 0. conteos, nulos de amount_usd, montos <=0 ==")
print(q(f"""SELECT currency, count(*) n, count(amount_usd) nn_usd, round(100*(1-count(amount_usd)/count(*)),3) pct_null,
  sum((amount<=0)::INT) nonpos FROM tx GROUP BY 1 ORDER BY 1""").to_string(index=False))

print("\n== 1. pendiente ln(monto)/año por moneda x ttype con SE y z (process_date y ts) ==")
s = q("""WITH t AS (SELECT currency, ttype, ln(amount) y,
     date_diff('day', DATE '2023-06-17', process_date)/365.25 x1,
     (epoch(ts) - epoch(TIMESTAMP '2023-06-17 00:00:00'))/(365.25*86400) x2 FROM tx WHERE amount>0)
  SELECT currency, ttype, count(*) n, regr_slope(y,x1) b1, regr_r2(y,x1) r2_1, var_samp(y) vy, var_samp(x1) vx1,
         regr_slope(y,x2) b2, var_samp(x2) vx2, regr_r2(y,x2) r2_2 FROM t GROUP BY ALL ORDER BY 1,2""")
s['se1'] = np.sqrt((1-s.r2_1)*s.vy/((s.n-2)*s.vx1)); s['z1'] = s.b1/s.se1
s['se2'] = np.sqrt((1-s.r2_2)*s.vy/((s.n-2)*s.vx2)); s['z2'] = s.b2/s.se2
print(s[['currency','ttype','n','b1','se1','z1','r2_1','b2','z2']].round(5).to_string(index=False))
print("max|b| =", round(s.b1.abs().max(),5), " max R2 =", s.r2_1.max(), " max|z| =", round(s.z1.abs().max(),2),
      " #|z|>3 =", int((s.z1.abs()>3).sum()), "de", len(s))

print("\n== 2. topes y cuantiles por año (moneda x ttype): rango relativo entre años ==")
y = q("""SELECT currency, ttype, year(process_date) yr, count(*) n, min(amount) mn, max(amount) mx,
  quantile_cont(amount,0.1) p10, median(amount) p50, quantile_cont(amount,0.9) p90 FROM tx GROUP BY ALL""")
rows = []
for (c,t), g in y.groupby(['currency','ttype']):
    full = g[g.yr.isin([2024,2025])]
    rows.append(dict(currency=c, ttype=t, n_min_year=int(g.n.min()),
        min_by_year=f"{g.mn.min():.2f}-{g.mn.max():.2f}", max_by_year=f"{g.mx.min():.2f}-{g.mx.max():.2f}",
        p50_relrange_all=(g.p50.max()-g.p50.min())/g.p50.mean(), p50_relrange_2024_25=(full.p50.max()-full.p50.min())/full.p50.mean(),
        p90_relrange_all=(g.p90.max()-g.p90.min())/g.p90.mean()))
print(pd.DataFrame(rows).round(4).to_string(index=False))

print("\n== 3. mediana en USD-equivalente (amount/K) por moneda x ttype ==")
m = q(f"""SELECT ttype, currency, median(amount/{K}) med_usd_eq FROM tx GROUP BY ALL""")
print(m.pivot(index='ttype', columns='currency', values='med_usd_eq').round(1).to_string())

print("\n== 4. ¿el monto LOCAL depende del fx del día? pendiente ln(amount) ~ ln(fx/K) dentro de ttype ==")
print("   (0 = independiente; 1 = monto convertido con la tasa del día). Incluye USD vs USD->MXN como placebo.")
for dcol, lab in [("process_date", "process_date"), ("CAST(ts AS DATE)", "date(ts)")]:
    r = q(f"""WITH f AS (SELECT date, dst, rate FROM fx WHERE src='USD' AND dst IN ('ARS','COP','MXN')),
      t AS (SELECT tx.currency, tx.ttype, ln(tx.amount) y,
            ln(f.rate / (CASE f.dst WHEN 'ARS' THEN 350.0 WHEN 'COP' THEN 4000.0 ELSE 17.0 END)) x
            FROM tx JOIN f ON f.date = {dcol}
             AND f.dst = (CASE tx.currency WHEN 'USD' THEN 'MXN' ELSE tx.currency END)
            WHERE tx.amount>0)
      SELECT currency, ttype, count(*) n, regr_slope(y,x) b, regr_r2(y,x) r2, var_samp(y) vy, var_samp(x) vx FROM t GROUP BY ALL""")
    r['se'] = np.sqrt((1-r.r2)*r.vy/((r.n-2)*r.vx))
    out = []
    for c, g in r.groupby('currency'):
        w = 1/g.se**2; b = (g.b*w).sum()/w.sum(); se = np.sqrt(1/w.sum())
        out.append(dict(join=lab, currency=c, n=int(g.n.sum()), pooled_slope=b, se=se, ci95=f"[{b-1.96*se:.3f}, {b+1.96*se:.3f}]",
                        max_abs_slope_ttype=g.b.abs().max()))
    print(pd.DataFrame(out).round(4).to_string(index=False))

print("\n== 5. amount_usd: K fijo vs fx del día vs fx suavizado (media móvil 30d, media anual) ==")
r = q(f"""WITH f AS (SELECT date, dst, rate,
            avg(rate) OVER (PARTITION BY dst ORDER BY date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) ma30,
            avg(rate) OVER (PARTITION BY dst, year(date)) yavg
          FROM fx WHERE src='USD' AND dst IN ('ARS','COP')),
     t AS (SELECT tx.currency, tx.amount, tx.amount_usd, {K.replace('currency','tx.currency')} k, f.rate, f.ma30, f.yavg
          FROM tx JOIN f ON f.date = tx.process_date AND f.dst = tx.currency
          WHERE tx.amount_usd IS NOT NULL AND tx.currency IN ('ARS','COP'))
  SELECT currency, count(*) n,
    avg((amount_usd = round(amount/k,2))::INT) exact_K,
    avg((abs(amount_usd - amount/k) <= 0.005+1e-9)::INT) within_halfcent_K,
    avg((abs(amount_usd - amount/rate) <= 0.005+1e-9)::INT) within_halfcent_fxday,
    avg((abs(amount_usd - amount/ma30) <= 0.005+1e-9)::INT) within_halfcent_ma30,
    avg((abs(amount_usd - amount/yavg) <= 0.005+1e-9)::INT) within_halfcent_yavg,
    avg(abs(amount/k - amount_usd)/amount_usd) mape_K,
    avg(abs(amount/rate - amount_usd)/amount_usd) mape_fxday,
    avg(abs(amount/ma30 - amount_usd)/amount_usd) mape_ma30,
    avg(abs(amount/yavg - amount_usd)/amount_usd) mape_yavg,
    corr(amount_usd - amount/k, rate) corr_resid_fx,
    corr(amount/amount_usd, rate) corr_ratio_fx
  FROM t GROUP BY 1 ORDER BY 1""")
print(r.T.to_string())
print(q(f"""SELECT currency, avg(amount_usd/amount) mean_ratio, stddev(amount_usd/amount) sd_ratio,
   stddev(amount_usd/amount)/avg(amount_usd/amount) cv_ratio, avg(abs(amount_usd*{K}/amount - 1)) mean_abs_reldev,
   min(amount_usd - round(amount/{K},2)) min_resid_round, max(amount_usd - round(amount/{K},2)) max_resid_round
   FROM tx WHERE amount_usd IS NOT NULL GROUP BY 1 ORDER BY 1""").to_string(index=False))

print("\n== 6. fx: nivel, tendencia y centro (USD->X) ==")
f = q("""SELECT dst, date, rate FROM fx WHERE src='USD' AND dst IN ('ARS','COP','MXN') ORDER BY dst, date""")
cen = {'ARS':350.0,'COP':4000.0,'MXN':17.0}
for d, g in f.groupby('dst'):
    t = (pd.to_datetime(g.date) - pd.Timestamp('2023-06-17')).dt.days.values/365.25
    lr = np.log(g.rate.values); b = np.polyfit(t, lr, 1)[0]
    u = g.rate.values/cen[d]-1
    yr = g.assign(y=pd.to_datetime(g.date).dt.year).groupby('y').rate.mean().round(2).to_dict()
    print(f"USD->{d}: n={len(g)} media={g.rate.mean():.3f} (t vs centro={(g.rate.mean()-cen[d])/(g.rate.std()/np.sqrt(len(g))):.2f}) "
          f"min={g.rate.min():.3f} max={g.rate.max():.3f} u∈[{u.min():.4f},{u.max():.4f}] E|u|={np.abs(u).mean():.4f} "
          f"pendiente ln/año={b:.5f} ac1={np.corrcoef(lr[:-1], lr[1:])[0,1]:.3f} medias anuales={yr}")

print("\n== 7. nulos de amount_usd por moneda x año ==")
print(q("""SELECT currency, year(process_date) yr, round(100*avg((amount_usd IS NULL)::INT),2) pct_null FROM tx GROUP BY ALL""")
      .pivot(index='currency', columns='yr', values='pct_null').to_string())

print("\n== 8. estacionalidad del monto normalizado (monto / media de su moneda x ttype) por mes y día de semana ==")
base = f"""WITH mu AS (SELECT currency, ttype, avg(amount) m FROM tx GROUP BY ALL),
  t AS (SELECT tx.process_date d, tx.amount/mu.m r FROM tx JOIN mu USING (currency, ttype))"""
mm = q(base + " SELECT month(d) mo, count(*) n, avg(r) rel FROM t GROUP BY 1 ORDER BY 1")
dw = q(base + " SELECT dayofweek(d) dow, count(*) n, avg(r) rel FROM t GROUP BY 1 ORDER BY 1")
print("mes:", ' '.join(f"{int(a)}:{b:.4f}" for a, b in zip(mm.mo, mm.rel)), "| rango", round(mm.rel.max()-mm.rel.min(),4))
print("dow:", ' '.join(f"{int(a)}:{b:.4f}" for a, b in zip(dw.dow, dw.rel)), "| rango", round(dw.rel.max()-dw.rel.min(),4))
dd = q(base + " SELECT d, count(*) n, avg(r) rel FROM t GROUP BY 1")
print("diario: sd(rel)=", round(dd.rel.std(),4), " sd esperada por azar≈", round(np.sqrt((0.5**2) / dd.n.mean()),4),
      " (CV≈0.5 de uniforme ancha) ; corr(rel, t)=", round(np.corrcoef((pd.to_datetime(dd.d)-pd.Timestamp('2023-06-17')).dt.days, dd.rel)[0,1],4))

print("\n== 9. ¿inflación en otras tablas? pr: mediana de bal y credit_limit por moneda x año de apertura ==")
p = q("""SELECT currency, year(opened) yr, count(*) n, median(bal) med_bal, median(credit_limit) med_cl
  FROM pr WHERE opened IS NOT NULL GROUP BY ALL ORDER BY 1,2""")
print(p[p.n>=500].pivot(index='yr', columns='currency', values='med_bal').round(0).to_string())
sl = q("""SELECT currency, count(*) n, regr_slope(ln(bal), date_diff('day', DATE '2020-01-01', opened)/365.25) b_bal,
  regr_r2(ln(bal), date_diff('day', DATE '2020-01-01', opened)/365.25) r2_bal,
  min(opened) o0, max(opened) o1 FROM pr WHERE bal>0 AND opened IS NOT NULL GROUP BY 1""")
print(sl.round(5).to_string(index=False))
