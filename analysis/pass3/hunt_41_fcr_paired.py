"""hunt_41: IC95 bootstrap PAREADO de la ganancia de AUC al predecir FCR (resolved) sobre el baseline 'solo categoria':
+sentimiento, +duracion, +todo (itype, canal, espera, acentos, pais, segmento, hora, dia). Held-out 30% agrupado por cliente,
cc completo (686k). Ademas AUC de dur -> NO resuelto dentro de Transaccional con IC95.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_41_fcr_paired.py
"""
import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
df = con.execute("""SELECT c.customer_id, CAST(c.resolved AS INT) y, c.cat, c.sent, c.sent_score, c.itype, c.channel, c.dur, c.wait,
   c.c_acc, c.a_acc, u.country, u.segment, hour(c.ts) h, dayofweek(c.ts) dow
   FROM cc c LEFT JOIN cu u ON u.customer_id = c.customer_id""").df()
CATS = ['cat', 'sent', 'itype', 'channel', 'c_acc', 'a_acc', 'country', 'segment']
for c in CATS:
    df[c] = df[c].astype('category').cat.codes.replace(-1, np.nan).astype('float32')
tr, te = next(GroupShuffleSplit(1, test_size=0.3, random_state=7).split(df, df.y, df.customer_id.values))
yt = df.y.values[te]
sets = {'cat': ['cat'], 'cat+sent': ['cat', 'sent', 'sent_score'], 'cat+dur': ['cat', 'dur'],
        'todo': ['cat', 'sent', 'sent_score', 'itype', 'channel', 'dur', 'wait', 'c_acc', 'a_acc', 'country', 'segment', 'h', 'dow']}
P = {}
for name, fs in sets.items():
    m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, early_stopping=True, random_state=0,
                                       categorical_features=[i for i, f in enumerate(fs) if f in CATS] or None)
    m.fit(df[fs].values[tr], df.y.values[tr])
    P[name] = m.predict_proba(df[fs].values[te])[:, 1]
    print(f'{name:9s} AUC={roc_auc_score(yt, P[name]):.4f}', flush=True)
rng = np.random.default_rng(0)
B = {k: [] for k in ['cat+sent', 'cat+dur', 'todo']}
for _ in range(200):
    s = rng.integers(0, len(yt), len(yt))
    base = roc_auc_score(yt[s], P['cat'][s])
    for k in B:
        B[k].append(roc_auc_score(yt[s], P[k][s]) - base)
for k, v in B.items():
    print(f'ganancia {k} - cat: {np.mean(v):+.4f} IC95[{np.percentile(v,2.5):+.4f},{np.percentile(v,97.5):+.4f}]  n_test={len(te)}')
tcode = pd.Series(con.execute("SELECT DISTINCT cat FROM cc ORDER BY 1").df().cat).tolist()
cat_codes = dict(zip(sorted(tcode), range(len(tcode))))
m = (df.cat.values == cat_codes['Transaccional']) & ~np.isnan(df.dur.values)
yy, xx = 1 - df.y.values[m], df.dur.values[m]
bs = []
for _ in range(200):
    s = rng.integers(0, len(yy), len(yy)); bs.append(roc_auc_score(yy[s], xx[s]))
print(f'Transaccional: AUC dur -> NO resuelto = {roc_auc_score(yy, xx):.4f} IC95[{np.percentile(bs,2.5):.4f},{np.percentile(bs,97.5):.4f}] n={m.sum()} tasa_no_resuelto={yy.mean():.4f}')
