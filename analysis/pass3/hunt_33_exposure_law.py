"""hunt_33: ley de exposicion. Los unicos objetivos 'si/no' a nivel cliente que superan AUC 0.55 (victima de fraude,
reclamante repetido, alguna mora, alguna app vinculada) se explican por el NUMERO DE UNIDADES expuestas (tx, reclamos,
productos de credito, productos) con una tasa por unidad constante: P(>=1) = 1-(1-p)^k.
Compara en el MISMO held-out (30%, clientes) el GBM con ~200 features de todas las tablas vs la exposicion sola,
con IC95 bootstrap pareado de la diferencia; y calibra la formula 1-(1-p)^k (p estimado en train).
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_33_exposure_law.py
"""
import sys, time
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
sys.path.insert(0, 'analysis/pass3')
from hunt_common import load_cust, prep_X

d = load_cust()
ALL = [c for c in d.columns if c != 'customer_id']
credit_k = (d.pr_pt_1 + d.pr_pt_4 + d.pr_pt_5)
T = {
    # nombre: (y, exposicion k, prefijos/cols excluidas por tautologia)
    'victima_fraude (>=1 tx fraude)': ((d.tx_fraud > 0).astype(float).where(d.tx_n.notna()), d.tx_n,
                                      ('tx_fraud', 'txr_fraud', 'tx_fscore')),
    'reclamante_repetido (>=1 repeat)': (d.cp_repeat_any, d.cp_n, ('cp_repeat', 'has_cp')),
    'alguna_mora (>=1 prod credito dpd>0)': ((d.pr_dpd_pos > 0).astype(float).where(credit_k > 0), credit_k, ('pr_dpd',)),
    'alguna_app (>=1 prod con app)': ((d.pr_app_share > 0).astype(float).where(d.pr_n.notna()), d.pr_n, ('pr_app',)),
}
rng = np.random.default_rng(42)
for name, (y, k, excl) in T.items():
    t0 = time.time()
    m = y.notna() & k.notna()
    dd = d.loc[m]; yy = y[m].values.astype(int); kk = k[m].values.astype(float)
    feats = [c for c in ALL if not c.startswith(excl) and dd[c].nunique(dropna=True) > 1]
    X, cat_idx = prep_X(dd, feats)
    idx = rng.permutation(len(dd)); ntr = int(0.7 * len(dd)); tr, te = idx[:ntr], idx[ntr:]
    gbm = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, early_stopping=True, validation_fraction=0.15,
                                         n_iter_no_change=20, categorical_features=cat_idx or None, random_state=0)
    gbm.fit(X.iloc[tr], yy[tr])
    pg = gbm.predict_proba(X.iloc[te])[:, 1]
    # tasa por unidad estimada en train (maxima verosimilitud aproximada por momento: 1-(1-p)^k)
    from scipy.optimize import brentq
    f = lambda p: np.mean(1 - (1 - p) ** kk[tr]) - yy[tr].mean()
    p_hat = brentq(f, 1e-6, 0.999)
    pf = 1 - (1 - p_hat) ** kk[te]
    yt = yy[te]
    a_g, a_k = roc_auc_score(yt, pg), roc_auc_score(yt, kk[te])
    diffs = []
    for _ in range(300):
        s = rng.integers(0, len(yt), len(yt))
        if yt[s].min() == yt[s].max():
            continue
        diffs.append(roc_auc_score(yt[s], pg[s]) - roc_auc_score(yt[s], kk[te][s]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    # calibracion de la formula por k
    kb = pd.cut(kk[te], [0, 13, 26, 39, 52, 1e9], labels=['1-13', '14-26', '27-39', '40-52', '53+']).astype(str) if kk.max() > 20 else np.minimum(kk[te], 6)
    cal = pd.DataFrame({'k': kb, 'y': yt, 'pf': pf}).groupby('k').agg(n=('y', 'size'), obs=('y', 'mean'), formula=('pf', 'mean'))
    print(f"== {name}: n={len(dd)} positivos={yy.mean():.4f} p_por_unidad={p_hat:.5f}")
    print(f"   AUC GBM({len(feats)} feats)={a_g:.4f}  AUC exposicion sola={a_k:.4f}  dif GBM-exp={a_g-a_k:+.4f} IC95[{lo:+.4f},{hi:+.4f}]  ({time.time()-t0:.0f}s)")
    print('   calibracion P(>=1) por k (test):', cal.round(4).to_dict('index'), flush=True)
