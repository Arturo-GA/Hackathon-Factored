"""hunt_15: los objetivos 'predecibles' fraud_victim y repeat_complainer se explican solo por exposicion (n tx / n reclamos).
Compara AUC del GBM completo (hunt_04) con AUC de la variable de exposicion sola (mismo split no necesario: AUC univariante en todo el set + IC bootstrap)."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, 'analysis/pass3')
from hunt_common import boot_ci
from sklearn.metrics import roc_auc_score
d = pd.read_parquet('analysis/pass3/hunt_cache/cust_wide.parquet', columns=['customer_id', 'tx_n', 'tx_active_days', 'tx_fraud', 'cp_n', 'cp_repeat_any', 'tx_declined', 'tx_intl'])
m = d.tx_n.notna()
y = (d.tx_fraud[m] > 0).astype(int).values
for c in ['tx_n', 'tx_active_days']:
    x = d[c][m].values
    print(f'fraud_victim ~ {c}: AUC={roc_auc_score(y, x):.4f} IC95={np.round(boot_ci(y, x, roc_auc_score), 4)} n={m.sum()} pos={y.sum()}')
# esperado bajo modelo binomial p=0.001 por tx
p = 0.0010
pr = 1 - (1 - p) ** d.tx_n[m].values
print('AUC con prob. teorica 1-(1-p)^n:', round(roc_auc_score(y, pr), 4))
print('tasa de victima por tercil de n tx:', pd.Series(y).groupby(pd.qcut(d.tx_n[m].values, 3, labels=['bajo', 'medio', 'alto'])).agg(['mean', 'size']).round(4).to_dict())
mc = d.cp_n.notna()
y2 = d.cp_repeat_any[mc].astype(int).values
x2 = d.cp_n[mc].values
print(f'repeat_complainer ~ cp_n: AUC={roc_auc_score(y2, x2):.4f} IC95={np.round(boot_ci(y2, x2, roc_auc_score), 4)} n={mc.sum()}')
print('P(repeat_any) por cp_n:', pd.Series(y2).groupby(np.minimum(x2, 4)).agg(['mean', 'size']).round(4).to_dict(),
      ' esperado 1-(0.85)^k:', {k: round(1 - 0.85 ** k, 4) for k in range(1, 5)})
# mora a nivel cliente: exposicion por numero de productos de credito
e = pd.read_parquet('analysis/pass3/hunt_cache/cust_wide.parquet', columns=['pr_pt_1', 'pr_pt_4', 'pr_pt_5', 'pr_dpd_pos'])
k = (e.pr_pt_1 + e.pr_pt_4 + e.pr_pt_5)
mk = k > 0
y3 = (e.pr_dpd_pos[mk] > 0).astype(int).values
print(f'dpd_pos_cliente ~ n_productos_credito: AUC={roc_auc_score(y3, k[mk].values):.4f} IC95={np.round(boot_ci(y3, k[mk].values, roc_auc_score), 4)} n={mk.sum()}')
print('P(algun dpd>0) por n credito:', pd.Series(y3).groupby(np.minimum(k[mk].values, 4)).agg(['mean', 'size']).round(4).to_dict(),
      ' esperado 1-(1-0.1418)^k:', {j: round(1 - (1 - 0.1418) ** j, 4) for j in range(1, 5)})
