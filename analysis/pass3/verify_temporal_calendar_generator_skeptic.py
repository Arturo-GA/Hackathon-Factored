"""Verificador escéptico: temporal_calendar_generator.
Ataques: (1) ¿process_date es derivado de ts (offset horario) -> 'artefacto lunes' = mezcla trivial?
(2) igualdad lun-vie y sáb=dom con tamaño de efecto; (3) ¿multiplicador realmente U(0.8,1.2)*Poisson o conteo exacto?
tendencia, feriados; (4) independencia entre tablas incl. sv<-cc (sv se asocia a interacciones cc) y rezagos;
(5) ¿algún modelo con features de calendario supera las dos medias?"""
import duckdb, pandas as pd, numpy as np
from scipy import stats
rng = np.random.default_rng(7)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
idx = pd.date_range('2023-06-17', '2026-06-17')

print("== 1. offset ts - process_date (h) por tabla")
for t in ['tx', 'cc', 'cp', 'sv']:
    r = q(f"""SELECT min(epoch(ts)-epoch(process_date::TIMESTAMP))/3600 mn, max(epoch(ts)-epoch(process_date::TIMESTAMP))/3600 mx,
            avg((ts::DATE<>process_date)::INT) shift FROM {t}""")
    print(t, r.round(3).to_dict('records'))

def daily(t, expr='process_date', where=''):
    d = q(f"SELECT {expr} d, count(*) n FROM {t} {where} GROUP BY 1"); d['d'] = pd.to_datetime(d.d)
    return d.set_index('d').n.reindex(idx).astype(float)

S = {t: daily(t) for t in ['tx', 'cc', 'cp', 'sv']}
S['tx_decl'] = daily('tx', where="WHERE status='Declined'")
S['de'] = daily('de', 'CAST(ts AS DATE)')
S['tr'] = daily('tr t JOIN cc c USING(interaction_id)', 'c.process_date')
D = pd.DataFrame(S)
print("días extremos (posibles parciales):", D.iloc[[0, 1, -2, -1]].to_dict('index'))
D = D.iloc[1:-1]
dow = D.index.dayofweek; we = np.asarray(dow >= 5)

print("\n== 2. perfil por día de la semana (process_date), relativo a media lun-vie")
for t in D.columns:
    s = D[t]; prof = s.groupby(dow).mean() / s[~we].mean()
    kw = stats.kruskal(*[s[dow == k].values for k in range(5)]).pvalue
    satsun = stats.mannwhitneyu(s[dow == 5], s[dow == 6]).pvalue
    print(f"{t:8s} lun..dom={prof.round(3).tolist()} rango lun-vie={prof[:5].max()-prof[:5].min():.3f} KW p={kw:.2f} sab=dom p={satsun:.2f} finde/sem={s[we].mean()/s[~we].mean():.4f}")

print("\n== 2b. razón finde/semana por país en tx y por motivo en cc")
g = q("SELECT country, dayofweek(process_date) IN (0,6) we, count(*) n FROM tx WHERE process_date BETWEEN '2023-06-18' AND '2026-06-16' GROUP BY ALL")
p = g.pivot(index='country', columns='we', values='n'); nwe = we.sum(); nwd = (~we).sum()
print(((p[True] / nwe) / (p[False] / nwd)).round(3).to_dict())
g = q("SELECT contact_reason k, dayofweek(process_date) IN (0,6) we, count(*) n FROM cc WHERE process_date BETWEEN '2023-06-18' AND '2026-06-16' GROUP BY ALL")
p = g.pivot(index='k', columns='we', values='n'); rr = ((p[True] / nwe) / (p[False] / nwd))
print("cc por contact_reason finde/sem: min=%.3f max=%.3f n_motivos=%d" % (rr.min(), rr.max(), len(rr)))

print("\n== 3. residuo diario")
R = pd.DataFrame(index=D.index)
for t in D.columns:
    s = D[t]; R[t] = np.where(we, s / s[we].mean(), s / s[~we].mean())
for t in ['tx', 'cc', 'cp', 'sv']:
    r = R[t]; base = np.where(we, D[t][we].mean(), D[t][~we].mean())
    sdp = np.mean(1 / np.sqrt(base))
    exp_out = 2 * sdp * 0.3989 / 0.4 * len(r)
    yr = r.groupby(r.index.year).mean().round(4).to_dict()
    h, _ = np.histogram(r, bins=np.linspace(0.8, 1.2, 9))
    print(f"{t}: min={r.min():.4f} max={r.max():.4f} sd={r.std():.4f} (U teórica {0.4/np.sqrt(12):.4f}, Poisson {sdp:.4f}) fuera=[{(r<0.8).sum()},{(r>1.2).sum()}] esperado_fuera_si_Poisson~{exp_out:.1f} hist={h.tolist()} media/año={yr}")
    print(f"    base entre semana={D[t][~we].mean():.1f} finde={D[t][we].mean():.1f}; min/max conteo entre semana={D[t][~we].min():.0f}/{D[t][~we].max():.0f}; finde={D[t][we].min():.0f}/{D[t][we].max():.0f}")
for t in ['tx', 'cc']:
    sl = stats.linregress(np.arange(len(R)), R[t]); print(f"tendencia {t}: pendiente/año={sl.slope*365:.4f} p={sl.pvalue:.3f}")

print("\n== 3b. feriados (residuo medio)")
hol = {'01-01': 'Año nuevo', '12-25': 'Navidad', '12-24': 'Nochebuena', '12-31': 'Nochevieja', '05-01': 'Trabajo',
       '09-16': 'Indep MX', '07-20': 'Indep CO', '05-25': 'Rev Mayo AR', '07-09': 'Indep AR'}
md = np.asarray(D.index.strftime('%m-%d'))
for k, v in hol.items():
    m = md == k
    print(f"  {v:12s} n={m.sum()} tx={R.tx[m].mean():.3f} cc={R.cc[m].mean():.3f}")
allh = np.isin(md, list(hol))
print("  todos feriados: tx=%.4f±%.4f cc=%.4f±%.4f (n=%d)" % (R.tx[allh].mean(), 1.96*R.tx[allh].std()/np.sqrt(allh.sum()), R.cc[allh].mean(), 1.96*R.cc[allh].std()/np.sqrt(allh.sum()), allh.sum()))
for t in ['tx', 'cc', 'cp']:
    print("  ANOVA residuo %s ~ mes p=%.3f; ~ día del mes p=%.3f" % (t, stats.f_oneway(*[g.values for _, g in R[t].groupby(R.index.month)]).pvalue, stats.f_oneway(*[g.values for _, g in R[t].groupby(R.index.day)]).pvalue))

print("\n== 4. correlación de residuos entre series (mismo día) y rezagos")
print(R.corr().round(3).to_string())
print("SE aprox corr = %.3f" % (1 / np.sqrt(len(R))))
for a, b in [('tx', 'cc'), ('tx_decl', 'cc'), ('tx', 'cp'), ('cc', 'sv'), ('cc', 'cp'), ('tx', 'de'), ('cc', 'de')]:
    print(f"  {a}(t)->{b}(t+L): " + ", ".join(f"L{L}={R[a].corr(R[b].shift(-L)):.3f}" for L in [0, 1, 2, 3, 7]))
print("sv mismo process_date que su cc:", q("SELECT avg((s.process_date=c.process_date)::INT) same, count(*) n FROM sv s JOIN cc c USING(interaction_id)").round(4).to_dict('records'))

print("\n== 5. pronóstico: dos medias vs GBM con calendario+rezagos (test >= 2025-06-17)")
from sklearn.ensemble import GradientBoostingRegressor
cut = pd.Timestamp('2025-06-17')
def mape(y, yh): return np.mean(np.abs(y - yh) / y) * 100
for t in ['tx', 'cc', 'cp']:
    s = D[t]; trm = np.asarray(s.index < cut); tem = ~trm
    mT = s[trm & we].mean(); mF = s[trm & ~we].mean()
    yh2 = np.where(we[tem], mT, mF); yh2tr = np.where(we[trm], mT, mF)
    X = pd.DataFrame({'dow': dow, 'dom': D.index.day, 'mon': D.index.month, 'doy': D.index.dayofyear, 't': np.arange(len(D)),
                      'lag1': R[t].shift(1).values, 'lag7': R[t].shift(7).values, 'txr': R['tx'].shift(1).values, 'ccr': R['cc'].shift(1).values}, index=D.index).fillna(1)
    gb = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=0.03, subsample=0.8, random_state=0).fit(X[trm], s[trm])
    yhg = gb.predict(X[tem])
    cs = np.linspace(0.9, 1.05, 151)
    c = cs[np.argmin([mape(s[trm].values, c_ * yh2tr) for c_ in cs])]
    yt = s[tem].values
    e2 = np.abs(yt - yh2) / yt; eg = np.abs(yt - yhg) / yt
    bs = [np.mean((eg - e2)[ii]) * 100 for ii in (rng.integers(0, len(e2), len(e2)) for _ in range(2000))]
    print(f"  {t}: dos medias={mape(yt, yh2):.2f}% | x{c:.3f} (MAPE-óptimo train)={mape(yt, c*yh2):.2f}% | GBM={mape(yt, yhg):.2f}% dif GBM-2medias IC95=[{np.percentile(bs,2.5):.2f},{np.percentile(bs,97.5):.2f}] pp")
u = rng.uniform(0.8, 1.2, 10**6)
print("  piso U(0.8,1.2): pred=1 -> %.2f%%; pred óptima -> %.2f%%" % (np.mean(np.abs(u - 1) / u) * 100, min(np.mean(np.abs(u - c) / u) * 100 for c in np.linspace(0.9, 1.05, 151))))
