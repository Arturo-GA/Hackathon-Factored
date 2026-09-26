"""H20: reglas del generador de calendario, con IC bootstrap sobre días:
 - razón fin de semana/entre semana por tabla (tx, cc, cp, sv), igualdad lun..vie (con process_date) y artefacto con ts::DATE
 - multiplicador diario ~ U(0.8,1.2): KS contra simulación U(0.8,1.2)*Poisson
 - ANOVA del residuo por día del mes (quincena/fin de mes) y mezcla ttype x día del mes (V), monto de depósitos por día del mes
 - canal Branch/ATM por hora local (¿sucursal abierta 24h?)"""
import duckdb, pandas as pd, numpy as np
from scipy import stats
pd.set_option('display.width', 250)
rng = np.random.default_rng(0)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
idx = pd.date_range('2023-06-17', '2026-06-17')
for t in ['tx', 'cc', 'cp', 'sv']:
    for base in ['process_date', 'CAST(ts AS DATE)']:
        d = con.execute(f"SELECT {base} d, count(*) n FROM {t} GROUP BY 1").fetchdf(); d['d'] = pd.to_datetime(d.d)
        s = d.set_index('d').n.reindex(idx).dropna()
        wk = s.index.dayofweek >= 5
        boots = []
        a, b = s[wk].values, s[~wk].values
        for _ in range(1000):
            boots.append(rng.choice(a, len(a)).mean()/rng.choice(b, len(b)).mean())
        prof = s.groupby(s.index.dayofweek).mean(); prof = prof/prof[:5].mean()
        f = stats.f_oneway(*[s[s.index.dayofweek == k].values for k in range(5)])
        print(f"{t:3s} {base:18s} finde/semana={a.mean()/b.mean():.4f} IC95=[{np.percentile(boots,2.5):.4f},{np.percentile(boots,97.5):.4f}]  lun..dom/media(lun-vie)={list(prof.round(3))}  ANOVA lun-vie p={f.pvalue:.3g}")
# multiplicador diario
d = con.execute("SELECT process_date d, count(*) n FROM tx GROUP BY 1").fetchdf(); d['d'] = pd.to_datetime(d.d); s = d.set_index('d').n.reindex(idx)
wk = s.index.dayofweek >= 5
base_wd = s[~wk].mean(); base_we = s[wk].mean()
r = np.where(wk, s/base_we, s/base_wd)
sim = rng.uniform(0.8, 1.2, 200000); lam = np.where(rng.random(200000) < 2/7, base_we, base_wd); simr = rng.poisson(lam*sim)/lam
print("KS residuo tx vs U(0.8,1.2)+Poisson:", stats.ks_2samp(r, simr), " min/max residuo", r.min().round(4), r.max().round(4))
print("KS vs normal misma sd:", stats.ks_2samp(r, rng.normal(1, r.std(), 200000)))
dd = pd.DataFrame({'r': r, 'dom': s.index.day, 'eom': (s.index + pd.Timedelta(days=1)).day == 1})
f = stats.f_oneway(*[g.r.values for _, g in dd.groupby('dom')]); print("ANOVA residuo ~ día del mes: F=%.3f p=%.3f" % (f.statistic, f.pvalue))
for lab, m in [('dia1', dd.dom == 1), ('dia15', dd.dom == 15), ('dia30', dd.dom == 30), ('fin_mes', dd.eom), ('dias 14-16', dd.dom.isin([14, 15, 16])), ('dias 28-31+1-2', dd.dom.isin([28, 29, 30, 31, 1, 2]))]:
    x = dd.r[m]; print(f"  {lab}: n_dias={m.sum()} media residuo={x.mean():.4f} IC95=±{1.96*x.std()/np.sqrt(m.sum()):.4f}")
g = con.execute("SELECT day(process_date) dom, ttype, count(*) n FROM tx GROUP BY ALL").fetchdf().pivot(index='dom', columns='ttype', values='n')
chi = stats.chi2_contingency(g.values); print("ttype x día del mes: V=%.4f p=%.3g" % (np.sqrt(chi[0]/(g.values.sum()*(min(g.shape)-1))), chi[1]))
print(con.execute("""SELECT CASE WHEN day(process_date) IN (1,2,15,16,30,31) THEN 'quincena' ELSE 'otro' END k, ttype, count(*) n, median(amount/CASE currency WHEN 'ARS' THEN 350 WHEN 'COP' THEN 4000 ELSE 1 END) med_usd_eq
   FROM tx WHERE ttype IN ('Deposit','Withdrawal','Payment') GROUP BY ALL ORDER BY 2,1""").fetchdf().round(2).to_string(index=False))
h = con.execute("SELECT channel, hour(ts - INTERVAL 6 HOUR) h, count(*) n FROM tx GROUP BY ALL").fetchdf().pivot(index='channel', columns='h', values='n')
hh = h.div(h.mean(axis=1), axis=0)
print("canal x hora local: min/max relativo por canal"); print(pd.DataFrame({'min': hh.min(axis=1), 'max': hh.max(axis=1), 'noche_0_6': h.iloc[:, :6].sum(axis=1)/h.sum(axis=1)}).round(3).to_string())
chi = stats.chi2_contingency(h.values); print("canal x hora: V=%.4f p=%.3g" % (np.sqrt(chi[0]/(h.values.sum()*(min(h.shape)-1))), chi[1]))
g = con.execute("SELECT channel, dayofweek(process_date) IN (0,6) we, count(*) n FROM tx GROUP BY ALL").fetchdf().pivot(index='channel', columns='we', values='n')
print("finde/semana por canal (ajustado 5/2 días):", (g[True]/2/(g[False]/5)).round(3).to_dict())
