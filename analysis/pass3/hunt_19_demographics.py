"""hunt_19: atributos demograficos multiclase (segment, gender, occupation, education_level, marital_status, document_type, cstatus)
predichos desde TODO el comportamiento (tx, cc, cp, sv, cs, de, pr) + resto de cu. GBM multiclase, AUC macro OVR con IC95 bootstrap.
Se reporta tambien la version SIN columnas de cu (solo comportamiento) para aislar senal conductual.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_19_demographics.py
"""
import sys, time
import numpy as np
import pandas as pd
sys.path.insert(0, 'analysis/pass3')
from hunt_common import load_cust, prep_X, src_of
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

d = load_cust()
ALL = [c for c in d.columns if c != 'customer_id']
BEHAV = [c for c in ALL if src_of(c) != 'cu']


def macro_auc(Y, P):
    return np.mean([roc_auc_score(Y[:, k], P[:, k]) for k in range(Y.shape[1]) if 0 < Y[:, k].sum() < len(Y)])


for target in ['segment', 'gender', 'occupation', 'education_level', 'marital_status', 'document_type', 'cstatus']:
    for label, feats in [('todo', [c for c in ALL if c != target]), ('solo_comport', BEHAV)]:
        t = time.time()
        m = d[target].notna()
        dd = d.loc[m]
        y = dd[target].cat.codes.values
        X, cat_idx = prep_X(dd, feats)
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=42)
        clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, early_stopping=True, validation_fraction=0.15,
                                             n_iter_no_change=15, categorical_features=cat_idx or None, random_state=0)
        clf.fit(Xtr, ytr)
        P = clf.predict_proba(Xte)
        Y = np.eye(P.shape[1])[yte]
        auc = macro_auc(Y, P)
        rng = np.random.default_rng(0)
        bs = []
        for _ in range(100):
            s = rng.choice(len(yte), len(yte))
            bs.append(macro_auc(Y[s], P[s]))
        acc = (P.argmax(1) == yte).mean()
        maj = np.bincount(yte).max() / len(yte)
        per = {str(dd[target].cat.categories[k]): round(roc_auc_score(Y[:, k], P[:, k]), 3) for k in range(P.shape[1]) if 0 < Y[:, k].sum() < len(Y)}
        extra = ''
        if np.percentile(bs, 2.5) > 0.53:
            # importancia: permutar cada feature en 8000 filas
            s = rng.choice(len(yte), 8000, replace=False)
            Xs = Xte.iloc[s].copy(); Ys = Y[s]
            base = macro_auc(Ys, clf.predict_proba(Xs))
            imp = {}
            for c in Xs.columns:
                Z = Xs.copy(); Z[c] = Z[c].values[rng.permutation(len(Z))]
                imp[c] = base - macro_auc(Ys, clf.predict_proba(Z))
            extra = ' top=' + str([(k, round(v, 4)) for k, v in sorted(imp.items(), key=lambda kv: -kv[1])[:6]])
        print(f"{target} [{label}] macroAUC={auc:.4f} IC95[{np.percentile(bs,2.5):.4f},{np.percentile(bs,97.5):.4f}] acc={acc:.4f} mayoritaria={maj:.4f} n_te={len(yte)} por_clase={per}{extra} ({time.time()-t:.0f}s)", flush=True)
