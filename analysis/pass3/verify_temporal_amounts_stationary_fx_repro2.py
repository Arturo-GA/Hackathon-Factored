"""Verificacion independiente (reintento): temporal_amounts_stationary_fx.
Afirmaciones: (1) montos estacionarios por moneda x ttype (|pendiente ln(monto)/anio|<=0.011, R2<2e-4);
(2) fx sin devaluacion (USD->ARS ~350, USD->COP ~4000); (3) amount_usd = amount/350 (ARS), amount/4000 (COP),
no con fx diario (~1% de error); (4) amount_usd nulo 100% en USD, ~5% en ARS/COP estable por anio;
(5) mediana en USD equivalente igual entre monedas (monto generado en USD y convertido)."""
import sys
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).fetchdf()
SEC = sys.argv[1] if len(sys.argv) > 1 else 'ALL'
RATE = "CASE currency WHEN 'ARS' THEN 350.0 WHEN 'COP' THEN 4000.0 ELSE 1.0 END"

if SEC in ('ALL', 'A'):
    print("== A. conteos, signo de amount y nulos por moneda")
    print(Q("""SELECT currency, count(*) n, sum((amount<=0)::INT) n_nonpos, sum((amount IS NULL)::INT) n_null,
        min(amount) mn, max(amount) mx, avg((amount_usd IS NULL)::INT) usd_null_rate,
        sum((amount_usd IS NOT NULL)::INT) n_usd_notnull FROM tx GROUP BY 1 ORDER BY 1""").to_string(index=False))
    print(Q("""SELECT country, currency, count(*) n FROM tx GROUP BY ALL ORDER BY 1,2""").to_string(index=False))

if SEC in ('ALL', 'B'):
    print("\n== B. pendiente de ln(amount) por anio (process_date y ts), por moneda x ttype, con SE")
    s = Q("""WITH d AS (SELECT currency, ttype, ln(amount) y,
                 (process_date - DATE '2023-06-17')/365.25 x1,
                 (epoch(ts) - epoch(TIMESTAMP '2023-06-17'))/31557600.0 x2 FROM tx WHERE amount>0)
        SELECT currency, ttype, count(*) n,
          regr_slope(y,x1) b_pd, regr_r2(y,x1) r2_pd,
          sqrt((regr_syy(y,x1) - regr_slope(y,x1)*regr_sxy(y,x1))/(count(*)-2)/regr_sxx(y,x1)) se_pd,
          regr_slope(y,x2) b_ts, regr_r2(y,x2) r2_ts
        FROM d GROUP BY ALL ORDER BY 1,2""")
    s['z_pd'] = s.b_pd / s.se_pd
    s['ci_lo'] = s.b_pd - 1.96*s.se_pd; s['ci_hi'] = s.b_pd + 1.96*s.se_pd
    print(s.to_string(index=False, float_format=lambda v: f"{v:.6g}"))
    print("max|b_pd|=%.5f  max r2_pd=%.2e  max|b_ts|=%.5f  max r2_ts=%.2e" % (s.b_pd.abs().max(), s.r2_pd.max(), s.b_ts.abs().max(), s.r2_ts.max()))
    print("celdas con |z|>3:", int((s.z_pd.abs() > 3).sum()), "de", len(s))
    # variacion total implicada en 3 anios (exp(3b)-1) para la celda con mayor |b|
    i = s.b_pd.abs().idxmax(); print("celda max |b|:", s.loc[i, ['currency','ttype','n','b_pd','se_pd']].to_dict(), " cambio 3a=%.2f%%" % (100*(np.exp(3*s.loc[i,'b_pd'])-1)))

if SEC in ('ALL', 'C'):
    print("\n== C. medianas y p90 trimestrales por moneda x ttype")
    m = Q("""SELECT currency, ttype, date_trunc('quarter', process_date) qt, count(*) n, median(amount) med,
             quantile_cont(amount, 0.9) p90, avg(amount) mean FROM tx WHERE amount>0 GROUP BY ALL""")
    full = m[(m.qt >= pd.Timestamp('2023-07-01')) & (m.qt <= pd.Timestamp('2026-01-01'))]
    for lab, dd in (('todos los trimestres', m), ('solo trimestres completos 2023Q3-2026Q1', full)):
        g = dd.groupby(['currency','ttype']).agg(nq=('med','size'), nmin=('n','min'), med_min=('med','min'), med_max=('med','max'),
                                                 p90_min=('p90','min'), p90_max=('p90','max'))
        g['med_rel_range_%'] = 100*(g.med_max/g.med_min - 1); g['p90_rel_range_%'] = 100*(g.p90_max/g.p90_min - 1)
        print('--', lab); print(g.round(2).to_string())
    # correlacion de rango (Spearman) mediana ~ trimestre, compras
    from scipy.stats import spearmanr
    for c in ['ARS','COP','USD']:
        d = full[(full.currency==c) & (full.ttype=='Purchase')].sort_values('qt')
        r, p = spearmanr(np.arange(len(d)), d.med.values)
        print(f"Purchase {c}: Spearman(mediana, trimestre)={r:.3f} p={p:.3f}; primer vs ultimo trimestre completo: {d.med.iloc[0]:.1f} -> {d.med.iloc[-1]:.1f}")
    print("-- mediana por anio calendario (ts) Purchase")
    print(Q("""SELECT currency, year(ts) y, count(*) n, median(amount) med, quantile_cont(amount,0.1) p10, quantile_cont(amount,0.9) p90
             FROM tx WHERE ttype='Purchase' GROUP BY ALL ORDER BY 1,2""").round(1).to_string(index=False))

if SEC in ('ALL', 'D'):
    print("\n== D. fx: pares, niveles y tendencia")
    print(Q("""SELECT src, dst, count(*) n, min(date) d0, max(date) d1, avg(rate) mean, stddev(rate) sd, min(rate) mn, max(rate) mx,
             regr_slope(ln(rate), (date - DATE '2023-06-17')/365.25) b_ln_yr, regr_r2(ln(rate), (date - DATE '2023-06-17')/365.25) r2
             FROM fx GROUP BY ALL ORDER BY 1,2""").to_string(index=False, float_format=lambda v: f"{v:.6g}"))
    qf = Q("""SELECT dst, date_trunc('quarter', date) qt, avg(rate) r FROM fx WHERE src='USD' GROUP BY ALL""")
    print("medias trimestrales USD->X (min, max):")
    print(qf.groupby('dst').r.agg(['min','max','count']).round(2).to_string())
    print("medias anuales USD->X:")
    print(Q("""SELECT dst, year(date) y, avg(rate) r FROM fx WHERE src='USD' GROUP BY ALL""").pivot(index='dst', columns='y', values='r').round(2).to_string())
    print("autocorrelacion lag-1 de la tasa diaria (ruido iid si ~0):")
    print(Q("""WITH f AS (SELECT src, dst, rate, lag(rate) OVER (PARTITION BY src, dst ORDER BY date) pr FROM fx)
             SELECT src, dst, corr(rate, pr) ac1 FROM f GROUP BY ALL ORDER BY 1,2""").round(3).to_string(index=False))
    print("consistencia de pares inversos: rate(X->USD)*rate(USD->X):")
    print(Q("""SELECT a.src, avg(a.rate*b.rate) prod_mean, min(a.rate*b.rate) mn, max(a.rate*b.rate) mx
             FROM fx a JOIN fx b ON a.date=b.date AND a.src=b.dst AND a.dst=b.src WHERE a.dst='USD' GROUP BY 1""").round(4).to_string(index=False))
    print("desvio relativo medio de la tasa diaria respecto a 350/4000:")
    print(Q("""SELECT dst, avg(abs(rate/CASE dst WHEN 'ARS' THEN 350 ELSE 4000 END - 1)) mad_rel, stddev(rate)/avg(rate) cv
             FROM fx WHERE src='USD' AND dst IN ('ARS','COP') GROUP BY 1""").round(5).to_string(index=False))

if SEC in ('ALL', 'E'):
    print("\n== E. amount_usd vs tasa fija (todas las filas con amount_usd no nulo)")
    e = Q(f"""SELECT currency, count(*) n, avg(amount_usd/amount) ratio_mean, stddev(amount_usd/amount) ratio_sd,
             min(amount_usd/amount) ratio_min, max(amount_usd/amount) ratio_max,
             avg(abs(amount_usd*{RATE}/amount - 1)) relerr_mean, median(abs(amount_usd*{RATE}/amount - 1)) relerr_med,
             quantile_cont(abs(amount_usd*{RATE}/amount - 1), 0.99) relerr_p99, max(abs(amount_usd*{RATE}/amount - 1)) relerr_max,
             avg((amount_usd = round(amount/{RATE}, 2))::INT) exact_round2,
             max(abs(amount_usd - amount/{RATE})) maxabs_diff,
             avg((abs(amount_usd - amount/{RATE}) <= 0.005 + 1e-9)::INT) within_half_cent
             FROM tx WHERE amount_usd IS NOT NULL AND amount <> 0 GROUP BY 1 ORDER BY 1""")
    print(e.T.to_string())
    print("1/350=%.9f 1/4000=%.9f" % (1/350, 1/4000))
    print("tasa implicita amount/amount_usd (mediana y percentiles):")
    print(Q("""SELECT currency, median(amount/amount_usd) med, quantile_cont(amount/amount_usd, 0.001) p001,
             quantile_cont(amount/amount_usd, 0.999) p999 FROM tx WHERE amount_usd > 0 GROUP BY 1""").round(4).to_string(index=False))

if SEC in ('ALL', 'F'):
    print("\n== F. amount_usd vs conversion con fx diario (variantes)")
    f = Q(f"""WITH u AS (SELECT date, dst, rate, buy, sell FROM fx WHERE src='USD'),
                  v AS (SELECT date, src, rate FROM fx WHERE dst='USD'),
                  t AS (SELECT currency, amount, amount_usd, process_date pd, CAST(ts AS DATE) td FROM tx
                        WHERE amount_usd IS NOT NULL AND amount <> 0 AND currency IN ('ARS','COP'))
        SELECT t.currency, count(*) n,
          avg(abs(t.amount_usd*{RATE}/t.amount - 1)) mape_fija,
          avg(abs(t.amount_usd - t.amount/u1.rate)/abs(t.amount_usd)) mape_usdX_pd,
          avg(abs(t.amount_usd - t.amount/u2.rate)/abs(t.amount_usd)) mape_usdX_ts,
          avg(abs(t.amount_usd - t.amount/u3.rate)/abs(t.amount_usd)) mape_usdX_pd_menos1,
          avg(abs(t.amount_usd - t.amount/u1.buy)/abs(t.amount_usd)) mape_buy_pd,
          avg(abs(t.amount_usd - t.amount/u1.sell)/abs(t.amount_usd)) mape_sell_pd,
          avg(abs(t.amount_usd - t.amount*v1.rate)/abs(t.amount_usd)) mape_Xusd_pd,
          avg((abs(t.amount_usd - t.amount/u1.rate)/abs(t.amount_usd) < 0.001)::INT) share_fxpd_within_0p1pct,
          avg((abs(t.amount_usd*{RATE}/t.amount - 1) < 0.001)::INT) share_fija_within_0p1pct
        FROM t LEFT JOIN u u1 ON u1.date=t.pd AND u1.dst=t.currency
               LEFT JOIN u u2 ON u2.date=t.td AND u2.dst=t.currency
               LEFT JOIN u u3 ON u3.date=t.pd - 1 AND u3.dst=t.currency
               LEFT JOIN v v1 ON v1.date=t.pd AND v1.src=t.currency
        GROUP BY 1 ORDER BY 1""")
    print(f.T.to_string())

if SEC in ('ALL', 'G'):
    print("\n== G. amount_usd nulo por moneda x anio, y por ttype/status (ARS+COP)")
    print(Q("""SELECT currency, year(process_date) y, avg((amount_usd IS NULL)::INT) nr, count(*) n FROM tx GROUP BY ALL""")
          .pivot(index='currency', columns='y', values='nr').round(4).to_string())
    print(Q("""SELECT ttype, avg((amount_usd IS NULL)::INT) nr, count(*) n FROM tx WHERE currency<>'USD' GROUP BY 1 ORDER BY 1""").round(4).to_string(index=False))
    print(Q("""SELECT status, avg((amount_usd IS NULL)::INT) nr, count(*) n FROM tx WHERE currency<>'USD' GROUP BY 1 ORDER BY 1""").round(4).to_string(index=False))

if SEC in ('ALL', 'H'):
    print("\n== H. distribucion en USD equivalente (tasas fijas) por moneda")
    h = Q(f"""SELECT ttype, currency, count(*) n, quantile_cont(amount/{RATE}, [0.01,0.1,0.25,0.5,0.75,0.9,0.99]) q,
              min(amount/{RATE}) mn, max(amount/{RATE}) mx, avg(amount/{RATE}) mean FROM tx GROUP BY ALL ORDER BY 1,2""")
    qs = pd.DataFrame(h.q.tolist(), columns=['p01','p10','p25','p50','p75','p90','p99'])
    h = pd.concat([h.drop(columns='q'), qs], axis=1)
    print(h.round(2).to_string(index=False))
    # KS entre monedas en compras (muestra 100k c/u) en USD eq
    from scipy.stats import ks_2samp
    smp = {c: Q(f"SELECT v FROM (SELECT amount/{RATE} v FROM tx WHERE ttype='Purchase' AND currency='{c}') USING SAMPLE 100000 ROWS").v.values for c in ['ARS','COP','USD']}
    print("tamanos de muestra:", {k: len(v) for k, v in smp.items()})
    for a, b in [('ARS','USD'), ('COP','USD'), ('ARS','COP')]:
        r = ks_2samp(smp[a], smp[b]); print(f"KS Purchase USD-eq {a} vs {b}: D={r.statistic:.4f} p={r.pvalue:.3g}")

if SEC in ('ALL', 'I'):
    print("\n== I. estructura decimal: el monto local es USD(2 dec) x tasa fija?")
    print(Q(f"""SELECT currency, count(*) n,
             avg((abs(amount*100 - round(amount*100)) < 1e-6)::INT) amount_2dec,
             avg((abs(amount - round(amount)) < 1e-9)::INT) amount_int,
             avg((abs(amount/{RATE}*100 - round(amount/{RATE}*100)) < 1e-6)::INT) usdeq_2dec,
             avg((abs(amount_usd*100 - round(amount_usd*100)) < 1e-6)::INT) FILTER (WHERE amount_usd IS NOT NULL) amount_usd_2dec
             FROM tx GROUP BY 1 ORDER BY 1""").round(4).to_string(index=False))
    print(Q("""WITH u AS (SELECT date, dst, rate FROM fx WHERE src='USD')
             SELECT t.currency, avg((abs(t.amount/u.rate*100 - round(t.amount/u.rate*100)) < 1e-6)::INT) usd_fxdia_2dec
             FROM (SELECT * FROM tx WHERE currency IN ('ARS','COP') USING SAMPLE 200000 ROWS) t
             JOIN u ON u.date=t.process_date AND u.dst=t.currency GROUP BY 1""").round(4).to_string(index=False))

if SEC in ('ALL', 'J'):
    print("\n== J. precision del ratio, mecanismo de discrepancias de redondeo y mediana de amount_usd")
    print(Q(f"""SELECT currency, avg(amount_usd/amount) m, stddev(amount_usd/amount) sd, stddev(amount_usd/amount)/avg(amount_usd/amount) cv
             FROM tx WHERE amount_usd IS NOT NULL GROUP BY 1 ORDER BY 1""").to_string(index=False, float_format=lambda v: f"{v:.3e}"))
    print(Q(f"""SELECT currency, count(*) n_mismatch, min(abs(amount/{RATE} - amount_usd)) min_absdiff, max(abs(amount/{RATE} - amount_usd)) max_absdiff,
             avg(abs(amount/{RATE} - amount_usd)) mean_absdiff
             FROM tx WHERE amount_usd IS NOT NULL AND amount_usd <> round(amount/{RATE}, 2) GROUP BY 1 ORDER BY 1""").to_string(index=False, float_format=lambda v: f"{v:.6f}"))
    print("discrepancias = empates exactos x.xx5 (|dif|=0.005) resueltos distinto (half-even vs half-away). Tasa esperada 1/(2*tasa): ARS %.4f%%, COP %.4f%%" % (100/(2*350), 100/(2*4000)))
    print(Q("""SELECT currency, median(amount_usd) med_amount_usd, median(amount/CASE currency WHEN 'ARS' THEN 350.0 ELSE 4000.0 END) med_usdeq
             FROM tx WHERE ttype='Purchase' AND currency<>'USD' GROUP BY 1 ORDER BY 1""").round(2).to_string(index=False))

if SEC in ('ALL', 'K'):
    print("\n== K. regla exacta: amount_usd = redondeo a centavos half-to-even de amount/tasa?")
    k = Q(f"""SELECT currency, count(*) n,
             avg((amount_usd = round(amount/{RATE}, 2))::INT) eq_half_away,
             avg((amount_usd = round_even(amount/{RATE}, 2))::INT) eq_half_even,
             avg((abs(amount_usd - round_even(amount/{RATE}, 2)) < 1e-9)::INT) eq_half_even_tol
             FROM tx WHERE amount_usd IS NOT NULL GROUP BY 1 ORDER BY 1""")
    print(k.to_string(index=False, float_format=lambda v: f"{v:.6f}"))
    # en Python (round() de float, half-even sobre la representacion binaria) con muestra de discrepantes
    d = Q(f"""SELECT currency, amount, amount_usd FROM tx WHERE amount_usd IS NOT NULL AND amount_usd <> round(amount/{RATE}, 2)""")
    d['py'] = [round(a/(350.0 if c=='ARS' else 4000.0), 2) for a, c in zip(d.amount, d.currency)]
    print("discrepantes con round de DuckDB:", len(d), "; de ellos reproducidos por round() de Python:", int((abs(d.py - d.amount_usd) < 1e-9).sum()))
    # todas las filas no nulas (por lotes de 200k, sin cargar la tabla completa)
    tot = {}; ok = {}
    rdr = con.execute("SELECT currency, amount, amount_usd FROM tx WHERE amount_usd IS NOT NULL").fetch_record_batch(200000)
    for b in rdr:
        cur = b.column(0).to_pylist(); am = b.column(1).to_pylist(); us = b.column(2).to_pylist()
        for c, a, u in zip(cur, am, us):
            tot[c] = tot.get(c, 0) + 1
            ok[c] = ok.get(c, 0) + (round(a/(350.0 if c == 'ARS' else 4000.0), 2) == u)
    print("amount_usd == round(amount/tasa, 2) de Python (half-even exacto sobre el double):", {c: f"{ok[c]}/{tot[c]} = {ok[c]/tot[c]:.6f}" for c in tot})
