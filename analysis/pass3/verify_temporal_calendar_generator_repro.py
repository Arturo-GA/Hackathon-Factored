"""Verificación independiente: temporal_calendar_generator.
Volumen diario = base * (1 | factor finde) * U(0.8,1.2) iid, independiente entre tablas."""
import duckdb, pandas as pd, numpy as np
from scipy import stats
rng = np.random.default_rng(42)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

def daily(t, expr='process_date', where=''):
    d = con.execute(f"SELECT {expr} AS d, count(*) AS n FROM {t} {where} GROUP BY 1").fetchdf()
    d['d'] = pd.to_datetime(d.d)
    return d.set_index('d').n.sort_index()

series = {}
for t in ['tx', 'cc', 'cp', 'sv']:
    for expr in ['process_date', 'CAST(ts AS DATE)']:
        s = daily(t, expr)
        print(f"{t} {expr}: dias={len(s)} rango={s.index.min().date()}..{s.index.max().date()} extremos n={s.iloc[0]},{s.iloc[-1]} mediana={s.median():.0f}")
        # recortar extremos (posibles días parciales)
        s2 = s.iloc[1:-1]
        dow = s2.index.dayofweek
        wd = s2[dow < 5]; we = s2[dow >= 5]
        ratio = we.mean() / wd.mean()
        bs = [rng.choice(we.values, len(we)).mean() / rng.choice(wd.values, len(wd)).mean() for _ in range(2000)]
        prof = (s2.groupby(dow).mean() / wd.mean()).round(3).tolist()
        p = stats.f_oneway(*[s2[dow == k].values for k in range(5)]).pvalue
        p_kw = stats.kruskal(*[s2[dow == k].values for k in range(5)]).pvalue
        print(f"   finde/semana={ratio:.4f} IC95=[{np.percentile(bs,2.5):.4f},{np.percentile(bs,97.5):.4f}] perfil lun..dom={prof} ANOVA lun-vie p={p:.3g} KW p={p_kw:.3g}")
        if expr == 'process_date':
            series[t] = s2

# ---- residuo tx
s = series['tx']; dow = s.index.dayofweek; we = dow >= 5
base = np.where(we, s[we].mean(), s[~we].mean())
r = s.values / base
print(f"\nResiduo tx: min={r.min():.4f} max={r.max():.4f} sd={r.std():.4f} sd_poisson={np.mean(1/np.sqrt(base)):.4f}")
print(f"  sd teórica U(0.8,1.2)={0.4/np.sqrt(12):.4f}")
# distribución: fracción por deciles del rango [0.8,1.2]
h, _ = np.histogram(r, bins=np.linspace(0.8, 1.2, 9)); print("  hist 8 bins 0.8..1.2:", h.tolist(), " fuera:", int(((r < 0.8) | (r > 1.2)).sum()))
simU = rng.uniform(0.8, 1.2, 200000); lam = rng.choice(base, 200000); sim = rng.poisson(lam * simU) / lam
print("  KS vs U(0.8,1.2)*Poisson:", stats.ks_2samp(r, sim))
print("  KS vs Normal(1,sd):", stats.ks_2samp(r, rng.normal(1, r.std(), 200000)))
print(f"  kurtosis exceso={stats.kurtosis(r):.3f} (uniforme=-1.2, normal=0)")
rs = pd.Series(r, index=s.index)
full = rs.reindex(pd.date_range(rs.index.min(), rs.index.max()))
for lag in [1, 2, 7]:
    print(f"  autocorr lag{lag}={full.autocorr(lag):.4f}")
# base constante en el tiempo? tendencia por año
yr = pd.Series(r, index=s.index).groupby(s.index.year).mean(); print("  residuo medio por año:", yr.round(4).to_dict())
print("  corr(residuo, tiempo)=%.4f" % np.corrcoef(np.arange(len(r)), r)[0, 1])

# ---- residuos dentro de tx por ttype, currency, country, channel
def resid_by(col):
    d = con.execute(f"SELECT process_date d, {col} k, count(*) n FROM tx GROUP BY ALL").fetchdf()
    d['d'] = pd.to_datetime(d.d)
    p = d.pivot(index='d', columns='k', values='n').loc[s.index].astype(float)
    w = p.index.dayofweek >= 5
    res = p.copy()
    for c in p.columns:
        res.loc[w, c] = p.loc[w, c] / p.loc[w, c].mean(); res.loc[~w, c] = p.loc[~w, c] / p.loc[~w, c].mean()
    cm = res.corr().values; iu = np.triu_indices_from(cm, 1)
    # correlación esperada si solo Poisson: comparar con varianza
    print(f"  {col}: corr residuos media={cm[iu].mean():.3f} min={cm[iu].min():.3f}; finde/semana por grupo:", (p[w].mean() / p[~w].mean()).round(3).to_dict())
print("\nDentro de tx:")
for col in ['ttype', 'currency', 'channel', 'status']:
    resid_by(col)

# ---- entre tablas
res = {}
for t in ['tx', 'cc', 'cp', 'sv']:
    x = series[t]; w = x.index.dayofweek >= 5
    rr = x.astype(float).copy(); rr[w] = x[w] / x[w].mean(); rr[~w] = x[~w] / x[~w].mean(); res[t] = rr
for t, expr, wh in [('de', 'CAST(ts AS DATE)', ''), ('txdecl', 'process_date', '')]:
    pass
dx = daily('tx', 'process_date', "WHERE status='Declined'").iloc[1:-1]; w = dx.index.dayofweek >= 5
rr = dx.astype(float).copy(); rr[w] = dx[w] / dx[w].mean(); rr[~w] = dx[~w] / dx[~w].mean(); res['tx_declined'] = rr
de = daily('de', 'CAST(ts AS DATE)').iloc[1:-1]; w = de.index.dayofweek >= 5
print("\nde finde/semana=%.4f" % (de[w].mean() / de[~w].mean()))
rr = de.astype(float).copy(); rr[w] = de[w] / de[w].mean(); rr[~w] = de[~w] / de[~w].mean(); res['de'] = rr
R = pd.DataFrame(res).dropna()
print("Correlación residuos entre tablas (n días=%d):" % len(R)); print(R.corr().round(3).to_string())
# lag: tx(t) -> cc(t+1..t+3)
for L in [1, 2, 3, 7]:
    print(f"  corr tx_resid(t) vs cc_resid(t+{L})={R.tx.corr(R.cc.shift(-L)):.4f}; tx_declined(t) vs cc(t+{L})={R.tx_declined.corr(R.cc.shift(-L)):.4f}; tx vs cp(t+{L})={R.tx.corr(R.cp.shift(-L)):.4f}")

# ---- pronóstico
cut = pd.Timestamp('2025-06-17')
def mape(y, yh): return np.mean(np.abs(y - yh) / y) * 100
print("\nPronóstico (test >= 2025-06-17):")
for t in ['tx', 'cc', 'cp', 'sv']:
    x = series[t]; w = x.index.dayofweek >= 5
    tr = x[x.index < cut]; te = x[x.index >= cut]
    mw = tr[tr.index.dayofweek >= 5].mean(); md = tr[tr.index.dayofweek < 5].mean()
    yh = np.where(te.index.dayofweek >= 5, mw, md)
    # naive t-7
    full = x.reindex(pd.date_range(x.index.min(), x.index.max()))
    n7 = full.shift(7).reindex(te.index)
    ok = n7.notna()
    # dow mean (7 medias)
    dm = tr.groupby(tr.index.dayofweek).mean(); yh7 = dm.reindex(te.index.dayofweek).values
    # media móvil 28 días ajustada finde
    print(f"  {t}: dos medias MAPE={mape(te.values, yh):.2f}%  7 medias={mape(te.values, yh7):.2f}%  naive t-7={mape(te[ok].values, n7[ok].values):.2f}%  n_test={len(te)}")
# piso teórico: predecir la media cuando y = base*U -> E|U - E[U]|/U ; y con media óptima
u = rng.uniform(0.8, 1.2, 1_000_000)
print("  piso teórico MAPE (pred=1): %.2f%%; pred óptima MAPE (mediana ponderada) ~ %.2f%%" % (np.mean(np.abs(u - 1) / u) * 100, min(np.mean(np.abs(u - c) / u) * 100 for c in np.linspace(0.9, 1.05, 151))))
