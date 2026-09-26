"""Utilidades comunes hunt_*: carga de tabla ancha, GBM con held-out, IC95 bootstrap, importancia por grupos."""
import os
os.environ.setdefault('OMP_NUM_THREADS', '3')
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import roc_auc_score, r2_score
from sklearn.model_selection import GroupShuffleSplit

CACHE = 'analysis/pass3/hunt_cache'
CAT_COLS = ['document_type', 'gender', 'country', 'detected_accent', 'segment', 'occupation',
            'marital_status', 'education_level', 'cstatus', 'email_domain', 'state', 'city']


def load_cust():
    d = pd.read_parquet(f'{CACHE}/cust_wide.parquet')
    # contar NaN -> 0 en conteos de fuentes (NaN = cliente sin filas en esa tabla)
    for src, ncol in [('tx_', 'tx_n'), ('cc_', 'cc_n'), ('cp_', 'cp_n'), ('sv_', 'sv_n'), ('cs_', 'cs_n'), ('de_', 'de_n'), ('pr_', 'pr_n')]:
        d[f'has_{src[:-1]}'] = d[ncol].notna().astype('float32')
    n = d['tx_n'].fillna(0)
    for c in [c for c in d.columns if c.startswith(('tx_t_', 'tx_ch_', 'tx_cat_', 'tx_c', 'tx_declined', 'tx_pending', 'tx_reversed', 'tx_fraud', 'tx_foreign', 'tx_intl', 'tx_with'))]:
        if c in ('tx_cnull',) or d[c].dtype.kind == 'f':
            d[c.replace('tx_', 'txr_')] = (d[c] / n.replace(0, np.nan)).astype('float32')
    d['tx_decl_rate'] = d['tx_declined'] / d['tx_n']
    d['cc_per_tx'] = d['cc_n'] / d['tx_n']
    for c in CAT_COLS:
        d[c] = d[c].astype('category')
    return d


def src_of(col):
    for p in ['txr_', 'tx_', 'cc_', 'cp_', 'sv_', 'cs_', 'de_', 'pr_']:
        if col.startswith(p):
            return p.rstrip('_').replace('txr', 'tx')
    if col.startswith('has_'):
        return col[4:]
    return 'cu'


def prep_X(d, feats):
    X = d[feats].copy()
    cats = [c for c in feats if str(X[c].dtype) == 'category']
    for c in cats:
        X[c] = X[c].cat.codes.astype('float32').replace(-1, np.nan)
    return X, [feats.index(c) for c in cats]


def boot_ci(y, p, metric, n=200, seed=0):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(y))
    vals = []
    for _ in range(n):
        s = rng.choice(idx, len(idx), replace=True)
        try:
            vals.append(metric(y[s], p[s]))
        except ValueError:
            pass
    return np.percentile(vals, [2.5, 97.5])


def fit_eval(d, feats, y, kind='clf', groups=None, test_size=0.3, seed=42, perm_groups=True, top_feats=8,
             max_iter=300, sample_perm=20000):
    """kind: clf (binario), reg. Devuelve dict con metrica, IC, importancias por fuente y top features."""
    mask = ~pd.isna(y)
    d2 = d.loc[mask]
    yv = np.asarray(y[mask]).astype(float)
    feats = [c for c in feats if d2[c].nunique(dropna=True) > 1]  # quita columnas constantes / todo-NaN
    X, cat_idx = prep_X(d2, feats)
    g = groups[mask] if groups is not None else np.arange(len(d2))
    tr, te = next(GroupShuffleSplit(1, test_size=test_size, random_state=seed).split(X, yv, g))
    if kind == 'clf':
        m = HistGradientBoostingClassifier(max_iter=max_iter, learning_rate=0.08, early_stopping=True,
                                           validation_fraction=0.15, n_iter_no_change=20,
                                           categorical_features=cat_idx or None, random_state=seed)
        m.fit(X.iloc[tr], yv[tr])
        p = m.predict_proba(X.iloc[te])[:, 1]
        metric = roc_auc_score
    else:
        m = HistGradientBoostingRegressor(max_iter=max_iter, learning_rate=0.08, early_stopping=True,
                                          validation_fraction=0.15, n_iter_no_change=20,
                                          categorical_features=cat_idx or None, random_state=seed)
        m.fit(X.iloc[tr], yv[tr])
        p = m.predict(X.iloc[te])
        metric = r2_score
    yt = yv[te]
    score = metric(yt, p)
    lo, hi = boot_ci(yt, p, metric)
    out = dict(score=score, lo=lo, hi=hi, n_train=len(tr), n_test=len(te), pos_rate=float(np.mean(yt)) if kind == 'clf' else float(np.std(yt)))
    # importancia por permutacion (drop en metrica) sobre muestra del test
    rng = np.random.default_rng(1)
    s = rng.choice(len(te), min(sample_perm, len(te)), replace=False)
    Xs = X.iloc[te].iloc[s].copy()
    ys = yt[s]
    pred = (lambda Z: m.predict_proba(Z)[:, 1]) if kind == 'clf' else m.predict
    base = metric(ys, pred(Xs))
    imp = {}
    if perm_groups:
        srcs = {}
        for c in feats:
            srcs.setdefault(src_of(c), []).append(c)
        for sname, cols in srcs.items():
            Z = Xs.copy()
            perm = rng.permutation(len(Z))
            Z[cols] = Z[cols].values[perm]
            imp['SRC:' + sname] = base - metric(ys, pred(Z))
    signif = (kind == 'clf' and lo > 0.53) or (kind == 'reg' and lo > 0.01)
    if top_feats and (signif or top_feats < 0):
        top_feats = abs(top_feats)
        fi = {}
        for c in feats:
            Z = Xs.copy()
            Z[c] = Z[c].values[rng.permutation(len(Z))]
            fi[c] = base - metric(ys, pred(Z))
        top = sorted(fi.items(), key=lambda kv: -kv[1])[:top_feats]
        out['top'] = [(k, round(v, 4)) for k, v in top]
    out['src_imp'] = {k: round(v, 4) for k, v in sorted(imp.items(), key=lambda kv: -kv[1])}
    out['model'] = m
    out['p_test'] = p
    out['y_test'] = yt
    return out


def fmt(name, r, kind='AUC'):
    s = f"{name}: {kind}={r['score']:.4f} IC95[{r['lo']:.4f},{r['hi']:.4f}] ntr={r['n_train']} nte={r['n_test']} base={r['pos_rate']:.4f}"
    if 'src_imp' in r:
        s += f"\n   fuentes: {r['src_imp']}"
    if 'top' in r:
        s += f"\n   top: {r['top']}"
    return s
