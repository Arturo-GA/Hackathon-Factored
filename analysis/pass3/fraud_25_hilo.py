"""Dentro del fraude: ¿el fraude con fscore>30 difiere del fraude con fscore<=30/nulo? (modelo AUC) y correlación fscore~monto en fraude."""
import sys; sys.path.insert(0,'analysis/pass3')
import pandas as pd, numpy as np
from scipy.stats import spearmanr, chi2_contingency
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import cross_val_predict, GroupKFold
from sklearn.metrics import roc_auc_score
from fraud_00_common import connect, q
con = connect()
d = q(con, """SELECT t.customer_id, t.fscore, t.amount, t.ttype, t.channel, t.currency, t.status, hour(t.ts) hr, dayofweek(t.ts) dow, year(t.ts) yr, (t.country<>c.country) foreign_c,
  p.ptype, c.segment, date_diff('day', c.dob, t.ts::date)/365.25 age, c.credit_score, c.income, t.merchant_name IS NULL nom
  FROM tx t JOIN pr p USING(product_id) JOIN cu c ON c.customer_id=t.customer_id WHERE t.fraud""")
sc = d.dropna(subset=['fscore'])
print('spearman fscore~amount (fraude):', spearmanr(sc.fscore, sc.amount))
y = (d.fscore>30).astype(int).values
X = d.drop(columns=['customer_id','fscore']).copy()
for c in ['ttype','channel','currency','status','ptype','segment']: X[c]=X[c].astype('category').cat.codes
X = X.astype(float).values
p = cross_val_predict(HistGradientBoostingClassifier(max_iter=100, learning_rate=0.05, max_leaf_nodes=7, min_samples_leaf=50), X, y, cv=GroupKFold(5), groups=d.customer_id, method='predict_proba')[:,1]
auc = roc_auc_score(y,p); rng=np.random.default_rng(0)
bs=[roc_auc_score(y[i],p[i]) for i in (rng.integers(0,len(y),len(y)) for _ in range(300))]
print(f'fraude hi(>30) vs lo/nulo: n={len(y)} pos={y.sum()} AUC={auc:.3f} IC95=[{np.percentile(bs,2.5):.3f},{np.percentile(bs,97.5):.3f}]')
