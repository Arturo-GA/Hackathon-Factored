"""hunt_31: ¿el efecto del sentimiento sobre FCR (resolved) es real o confusion por categoria?
Transaccional es 100% Neutral y Producto 67% Neutral (hunt_30). Compara FCR por sentimiento DENTRO de categoria y
AUC held-out (agrupado por cliente) de: cat sola, cat+sent, cat+sent+itype+canal+dur+wait+pais+segmento.
Ademas: duracion por resolved dentro de Transaccional (por itype).
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_31_fcr_confound.py
"""
import sys
import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
sys.path.insert(0, 'analysis/pass3')
from hunt_common import boot_ci
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
print('(1) FCR por sentimiento dentro de categoria (tabla completa)')
d = con.execute("""SELECT cat, sent, count(*) n, avg(CASE WHEN resolved THEN 1.0 ELSE 0 END) fcr FROM cc GROUP BY 1,2""").df()
print(d.pivot(index='cat', columns='sent', values='fcr').round(4).to_string())
print(d.pivot(index='cat', columns='sent', values='n').to_string())
print('(2) AUC held-out por cliente (muestra 300k)')
df = con.execute("""SELECT c.customer_id, CAST(c.resolved AS INT) y, c.cat, c.sent, c.sent_score, c.itype, c.channel, c.dur, c.wait,
   c.c_acc, c.a_acc, u.country, u.segment, hour(c.ts) h, dayofweek(c.ts) dow
   FROM (SELECT * FROM cc USING SAMPLE 300000 ROWS) c LEFT JOIN cu u ON u.customer_id = c.customer_id""").df()
for c in ['cat', 'sent', 'itype', 'channel', 'c_acc', 'a_acc', 'country', 'segment']:
    df[c] = df[c].astype('category').cat.codes.replace(-1, np.nan)
g = df.customer_id.values
tr, te = next(GroupShuffleSplit(1, test_size=0.3, random_state=0).split(df, df.y, g))
sets = {'cat': ['cat'], 'sent': ['sent'], 'cat+sent': ['cat', 'sent'], 'cat+sent_score': ['cat', 'sent_score'],
        'cat+dur': ['cat', 'dur'], 'todo_sin_sent': ['cat', 'itype', 'channel', 'dur', 'wait', 'c_acc', 'a_acc', 'country', 'segment', 'h', 'dow'],
        'todo': ['cat', 'sent', 'sent_score', 'itype', 'channel', 'dur', 'wait', 'c_acc', 'a_acc', 'country', 'segment', 'h', 'dow']}
cats_all = {'cat', 'sent', 'itype', 'channel', 'c_acc', 'a_acc', 'country', 'segment'}
for name, fs in sets.items():
    X = df[fs]
    m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, early_stopping=True, random_state=0,
                                       categorical_features=[i for i, f in enumerate(fs) if f in cats_all] or None)
    m.fit(X.iloc[tr], df.y.iloc[tr])
    p = m.predict_proba(X.iloc[te])[:, 1]
    yt = df.y.iloc[te].values
    lo, hi = boot_ci(yt, p, roc_auc_score, n=200)
    print(f'{name:16s} AUC={roc_auc_score(yt, p):.4f} IC95[{lo:.4f},{hi:.4f}] n_te={len(te)}', flush=True)
print('(3) FCR vs sent_score dentro de categoria no-Transaccional (deciles)')
q = con.execute("""SELECT cat, ntile(5) OVER (PARTITION BY cat ORDER BY sent_score) qs, resolved FROM cc WHERE cat <> 'Transaccional'""").df()
print(q.groupby(['cat', 'qs']).resolved.mean().unstack().round(4).to_string())
print('(4) duracion en Transaccional por resolved x itype')
print(con.execute("""SELECT itype, resolved, count(dur) n, median(dur) med, avg(dur) av, quantile_cont(dur, [0.1,0.9]) q FROM cc
   WHERE cat='Transaccional' AND dur IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""").df().to_string())
print(con.execute("""SELECT cat, CAST(floor(dur/60) AS INT) AS min_b, count(*) n, avg(CASE WHEN resolved THEN 1.0 ELSE 0 END) fcr FROM cc
   WHERE dur IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""").df().pivot(index="min_b", columns="cat", values="fcr").round(3).to_string())
from sklearn.metrics import roc_auc_score as _auc
for c in ["Transaccional", "Producto", "Queja", "Técnico", "Comercial", "Retención"]:
    z = con.execute(f"SELECT CAST(resolved AS INT) y, dur FROM cc WHERE cat='{c}' AND dur IS NOT NULL").df()
    print(c, "AUC dur -> NO resuelto:", round(_auc(1 - z.y, z.dur), 4), "n=", len(z))
