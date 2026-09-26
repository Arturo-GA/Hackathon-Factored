"""Verificación (intento 2), complemento: factor de fin de semana estimado por rango medio (estimador casi exacto para uniformes),
valores extremos por clase, y estabilidad de la autocorrelación de tx por mitades."""
import duckdb, pandas as pd, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
IDX = pd.date_range('2023-06-17', '2026-06-17')
rng = np.random.default_rng(7)
S = {}
for t in ['tx', 'cc', 'cp', 'sv']:
    d = con.execute(f"SELECT process_date d, count(*) n FROM {t} GROUP BY 1").fetchdf(); d['d'] = pd.to_datetime(d.d)
    S[t] = d.set_index('d').n.reindex(IDX, fill_value=0).astype(float)
print("Factor finde por rango medio: base_clase = (max+min)/2 ; implica U en [min/base, max/base]")
for t, s in S.items():
    we = s.index.dayofweek >= 5
    out = []
    mids = {}
    for cls, m in [('lab', ~we), ('finde', we)]:
        x = s[m]; mid = (x.max() + x.min()) / 2; mids[cls] = mid
        out.append(f"{cls}: min={x.min():.0f} ({x.idxmin().date()}) max={x.max():.0f} ({x.idxmax().date()}) media={x.mean():.1f} rango_medio={mid:.1f} max/min={x.max()/x.min():.4f}")
    # IC del cociente de rangos medios por bootstrap paramétrico: simula U puro con las bases estimadas
    nwd, nwe = int((~we).sum()), int(we.sum())
    sims = []
    for _ in range(3000):
        a = np.round(mids['lab'] * rng.uniform(0.8, 1.2, nwd)); b = np.round(mids['finde'] * rng.uniform(0.8, 1.2, nwe))
        sims.append(((b.max() + b.min()) / 2) / ((a.max() + a.min()) / 2))
    sims = np.array(sims); r = mids['finde'] / mids['lab']
    print(f"{t}: " + " | ".join(out))
    print(f"    factor finde (rango medio) = {r:.4f}  IC95 aprox [{r - (np.percentile(sims,97.5)-np.median(sims)):.4f},{r + (np.median(sims)-np.percentile(sims,2.5)):.4f}]  (por medias: {s[we].mean()/s[~we].mean():.4f})")
# cp: distribución de conteos en los extremos
s = S['cp']; we = s.index.dayofweek >= 5
print("cp finde: conteos más bajos", sorted(s[we].values)[:6], "más altos", sorted(s[we].values)[-6:])
print("cp lab:   conteos más bajos", sorted(s[~we].values)[:6], "más altos", sorted(s[~we].values)[-6:])
# autocorrelación tx por mitades
def lb(x, H=14):
    x = np.asarray(x) - np.mean(x); n = len(x); den = (x * x).sum()
    ac = np.array([(x[k:] * x[:-k]).sum() / den for k in range(1, H + 1)])
    Q = n * (n + 2) * np.sum(ac ** 2 / (n - np.arange(1, H + 1))); return ac, Q, stats.chi2.sf(Q, H)
for t in ['tx', 'cc', 'cp']:
    s = S[t]; we = s.index.dayofweek >= 5
    r = s.copy(); r[we] = s[we] / s[we].mean(); r[~we] = s[~we] / s[~we].mean()
    half = len(r) // 2
    for lab, x in [('1a mitad', r.iloc[:half]), ('2a mitad', r.iloc[half:]), ('total', r)]:
        ac, Q, p = lb(x.values)
        print(f"{t} {lab}: lag1..7={np.round(ac[:7],3).tolist()} Q(14)={Q:.1f} p={p:.3f}")
    # permutación: p de Q(14) total por barajado de días (respeta la distribución marginal)
    _, Q0, _ = lb(r.values)
    Qp = [lb(rng.permutation(r.values))[1] for _ in range(1000)]
    print(f"{t}: p permutación Q(14) = {np.mean(np.array(Qp) >= Q0):.3f}")
