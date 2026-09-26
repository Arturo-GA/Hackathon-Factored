"""Parte 7: ¿señal geográfica débil en fraude? KS vs uniforme, réplica en mitades de clientes/tiempo, AUC con bootstrap por cliente."""
import duckdb, pandas as pd, numpy as np
from scipy import stats
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
df = pd.read_parquet('data/duckdb_tmp/verify_geo_s3.parquet')
print('filas', len(df), 'fraudes', df.y.sum())
f = df[df.y == 1]; l = df[df.y == 0]
# (a) KS of |dlat|, |dlon| for fraud against U(0,1)
for c in ['adlat', 'adlon']:
    ks = stats.kstest(f[c].clip(0, 1), 'uniform')
    ks_l = stats.kstest(l[c].sample(200000, random_state=0).clip(0, 1), 'uniform')
    print(f'{c}: fraude media={f[c].mean():.4f} (esperado 0.5, ee={0.2887/np.sqrt(len(f)):.4f}), KS p={ks.pvalue:.4g} | legit media={l[c].mean():.4f} KS p={ks_l.pvalue:.3g}')
# deciles of |dlon| for fraud
print('deciles |dlon| fraude (conteos, esperado ~77.5 c/u):', np.histogram(f.adlon, bins=np.linspace(0, 1, 11))[0])
print('deciles |dlat| fraude:', np.histogram(f.adlat, bins=np.linspace(0, 1, 11))[0])
# replicate by customer halves (hash) and by country
df['half'] = pd.util.hash_pandas_object(df.customer_id, index=False) % 2
for k, g in df[df.y == 1].groupby('half'):
    print(f'mitad {k}: n_fraude={len(g)} media |dlon|={g.adlon.mean():.4f} z={(g.adlon.mean()-0.5)/(0.2887/np.sqrt(len(g))):.2f}  media |dlat|={g.adlat.mean():.4f}')
for k, g in df[df.y == 1].groupby('cc'):
    print(f'{k}: n_fraude={len(g)} media |dlon|={g.adlon.mean():.4f} z={(g.adlon.mean()-0.5)/(0.2887/np.sqrt(len(g))):.2f}')
# AUC with cluster bootstrap (features are fixed transforms, no training => no leakage)
def auc_ci(y, s, groups, B=300, seed=0):
    rng = np.random.default_rng(seed)
    a = roc_auc_score(y, s)
    ug, inv = np.unique(groups, return_inverse=True)
    idx_by_g = pd.Series(np.arange(len(y))).groupby(inv).apply(np.array).values
    # stratified: resample customers; keep those with fraud always represented
    res = []
    G = len(ug)
    for _ in range(B):
        pick = rng.integers(0, G, G)
        ii = np.concatenate([idx_by_g[p] for p in pick])
        yy = y[ii]
        if yy.sum() == 0: continue
        res.append(roc_auc_score(yy, s[ii]))
    return a, np.percentile(res, 2.5), np.percentile(res, 97.5)
# subsample legit to keep bootstrap light: all frauds' customers + sample of others
rng = np.random.default_rng(1)
fc = set(df.loc[df.y == 1, 'customer_id'])
allc = df.customer_id.unique()
keep = set(rng.choice(allc, size=min(40000, len(allc)), replace=False)) | fc
d = df[df.customer_id.isin(keep)].reset_index(drop=True)
print('submuestra para AUC:', len(d), 'filas', d.y.sum(), 'fraudes', d.customer_id.nunique(), 'clientes')
y = d.y.values; g = d.customer_id.values
for name, s in [('-|dlon|', -d.adlon.values), ('-|dlat|', -d.adlat.values), ('-dist_centro', -np.hypot(d.adlat, d.adlon).values)]:
    a, lo, hi = auc_ci(y, s, g); print(f'AUC {name}: {a:.4f} [{lo:.4f}, {hi:.4f}]')
m = d.dprev.notna().values
for name, col in [('-dprev', 'dprev'), ('-dnext', 'dnext')]:
    mm = d[col].notna().values
    a, lo, hi = auc_ci(y[mm], -d.loc[mm, col].values, g[mm]); print(f'AUC {name}: {a:.4f} [{lo:.4f}, {hi:.4f}] n_fraude={y[mm].sum()}')
