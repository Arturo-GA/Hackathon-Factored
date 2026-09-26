"""hunt_40: a nivel producto, 'algun fraude' (AUC GBM 0.537 en hunt_06) vs exposicion (n tx del producto) sola.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_40_prod_fraud_exposure.py
"""
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
sys.path.insert(0, 'analysis/pass3')
from hunt_common import boot_ci
d = pd.read_parquet('analysis/pass3/hunt_cache/prod_wide.parquet', columns=['ptx_n', 'ptx_fraud', 'ptx_declined'])
d = d[d.ptx_n.notna()]
y = (d.ptx_fraud > 0).astype(int).values
x = d.ptx_n.values
print('productos con tx:', len(d), 'con >=1 fraude:', y.mean().round(5))
print('AUC n_tx ->algun fraude:', round(roc_auc_score(y, x), 4), 'IC95', np.round(boot_ci(y, x, roc_auc_score, n=200), 4))
p = d.ptx_fraud.sum() / d.ptx_n.sum()
print('p por tx:', round(p, 6))
cal = pd.DataFrame({'k': pd.cut(x, [0, 8, 11, 14, 17, 100]), 'y': y, 'f': 1 - (1 - p) ** x}).groupby('k', observed=True).agg(n=('y', 'size'), obs=('y', 'mean'), formula=('f', 'mean'))
print(cal.round(5).to_string())
yd = (d.ptx_declined > 0).astype(int).values
print('AUC n_tx -> algun rechazo:', round(roc_auc_score(yd, x), 4))
