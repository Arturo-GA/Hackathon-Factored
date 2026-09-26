"""Parte 9: modelo combinado de features geo para fraude (held-out agrupado por cliente) y réplica por mitades."""
import pandas as pd, numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
df = pd.read_parquet('data/duckdb_tmp/verify_geo_s3.parquet')
rng = np.random.default_rng(7)
fc = set(df.loc[df.y == 1, 'customer_id']); allc = df.customer_id.unique()
keep = set(rng.choice(allc, size=45000, replace=False)) | fc
d = df[df.customer_id.isin(keep)].reset_index(drop=True)
d['dprev_f'] = d.dprev.fillna(d.dprev.median()); d['dprev_na'] = d.dprev.isna().astype(int)
d['dnext_f'] = d.dnext.fillna(d.dnext.median()); d['dnext_na'] = d.dnext.isna().astype(int)
d['cc_ar'] = (d.cc == 'Argentina').astype(int); d['cc_co'] = (d.cc == 'Colombia').astype(int)
X = d[['adlat', 'adlon', 'dprev_f', 'dprev_na', 'dnext_f', 'dnext_na', 'cc_ar', 'cc_co']].values; y = d.y.values; g = d.customer_id.values
print('filas', len(d), 'fraudes', y.sum())
def boot(y, s, g, B=300, seed=0):
    r = np.random.default_rng(seed); ug, inv = np.unique(g, return_inverse=True)
    order = np.argsort(inv); bounds = np.searchsorted(inv[order], np.arange(len(ug) + 1))
    out = []
    for _ in range(B):
        pick = r.integers(0, len(ug), len(ug))
        ii = np.concatenate([order[bounds[p]:bounds[p + 1]] for p in pick])
        if y[ii].sum() > 0: out.append(roc_auc_score(y[ii], s[ii]))
    return np.percentile(out, [2.5, 97.5])
for name, mk in [('logística', lambda: LogisticRegression(max_iter=2000, class_weight='balanced')),
                 ('HGB', lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, class_weight='balanced'))]:
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(X, y, g):
        m = mk(); Xt = X[tr]; mu, sd = Xt.mean(0), Xt.std(0) + 1e-9
        m.fit((Xt - mu) / sd, y[tr]); oof[te] = m.predict_proba((X[te] - mu) / sd)[:, 1]
    lo, hi = boot(y, oof, g)
    print(f'{name} OOF AUC = {roc_auc_score(y, oof):.4f} [{lo:.4f}, {hi:.4f}]')
# halves replication of single-feature AUCs
d['half'] = pd.util.hash_pandas_object(d.customer_id, index=False) % 2
for h, gg in d.groupby('half'):
    m = gg.dprev.notna()
    print(f'mitad {h}: AUC -|dlon|={roc_auc_score(gg.y, -gg.adlon):.4f}  AUC -dprev={roc_auc_score(gg.y[m], -gg.dprev[m]):.4f}  n_fraude={gg.y.sum()}')
