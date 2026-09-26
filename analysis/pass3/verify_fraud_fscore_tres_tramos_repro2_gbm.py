"""Verificación (reintento), parte GBM: AUC de un GBM que solo ve fscore (nulo=-1).

En verify_fraud_fscore_tres_tramos_repro2.py el GBM entrenado sobre la tabla agregada con pesos enormes
(hasta ~1,200 por fila) divergió (AUC 0.32, predicciones ~0 en >30): artefacto de implementación.
Aquí se entrena sobre filas crudas: todo el fraude de los clientes de train + muestra de legítimas de train.
Se evalúa en TODAS las tx de los clientes de test (split propio hash(customer_id||'#v2') % 10 < 3)
con bootstrap Poisson por cliente.
"""
import time
import duckdb, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()
T0 = time.time()


def auc_hist(pos, neg):
    pos = np.asarray(pos, float); neg = np.asarray(neg, float)
    below = np.cumsum(neg) - neg
    return float((pos * (below + 0.5 * neg)).sum() / (pos.sum() * neg.sum()))


TEST = "hash(customer_id || '#v2') % 10 < 3"
trn = Q(f"""SELECT coalesce(fscore, -1.0) x, fraud::INT y FROM tx WHERE NOT ({TEST}) AND fraud
            UNION ALL
            SELECT x, y FROM (SELECT coalesce(fscore, -1.0) x, fraud::INT y FROM tx WHERE NOT ({TEST}) AND NOT fraud)
            USING SAMPLE 250000 ROWS (reservoir, 17)""")
print(f"train crudo: n={len(trn):,} fraude={int(trn.y.sum())}")
tst = Q(f"""SELECT coalesce(round(fscore*100)::INT, -100) k, sum(fraud::INT) pos, sum((NOT fraud)::INT) neg
            FROM tx WHERE {TEST} GROUP BY 1""").set_index('k').astype(float)
print(f"test completo: n={int(tst.values.sum()):,} fraude={int(tst.pos.sum())}")
keys = np.array(sorted(set(tst.index.values) | set(np.round(trn.x.values * 100).astype(int).tolist()) - {-100} | {-100}))
Xk = np.where(keys < 0, -1.0, keys / 100).reshape(-1, 1)

configs = {
    'como_original(200it,lr.05,15hojas,msl100)': dict(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=100, random_state=0),
    'default_sklearn': dict(random_state=0),
}
R = 200
for name, cfg in configs.items():
    m = HistGradientBoostingClassifier(**cfg).fit(trn[['x']].values, trn.y.values)
    pmap = pd.Series(m.predict_proba(Xk)[:, 1], index=keys).round(12)
    st = tst.assign(s=pmap.reindex(tst.index).values).groupby('s')[['pos', 'neg']].sum().sort_index()
    auc = auc_hist(st.pos, st.neg)
    le = pmap[(pmap.index >= 0) & (pmap.index <= 3000)]
    mapg = pd.DataFrame({'k': keys.astype(np.int32), 'g': pmap.rank(method='dense').astype(np.int32).values})
    con.register('mapg', mapg)
    t1 = time.time()
    bt = Q(f"""
    WITH t AS (SELECT hash(customer_id) hc, coalesce(round(fscore*100)::INT, -100) k, fraud::INT y, count(*) n
               FROM tx WHERE {TEST} GROUP BY ALL),
    t2 AS (SELECT hc, g, y, sum(n) n FROM t JOIN mapg USING (k) GROUP BY ALL),
    w AS (SELECT r.b, g, y, n, (hash(hc, r.b) % 1000000)::DOUBLE / 1e6 u FROM t2 CROSS JOIN range({R}) r(b))
    SELECT b, g, y, sum(n * CASE WHEN u < 0.3678794 THEN 0 WHEN u < 0.7357589 THEN 1 WHEN u < 0.9196986 THEN 2
        WHEN u < 0.9810118 THEN 3 WHEN u < 0.9963402 THEN 4 WHEN u < 0.9994058 THEN 5 ELSE 6 END)::BIGINT nw
    FROM w GROUP BY ALL""")
    con.unregister('mapg')
    gb = []
    for b, d in bt.groupby('b'):
        pv = d.pivot_table(index='g', columns='y', values='nw', aggfunc='sum', fill_value=0).sort_index()
        gb.append(auc_hist(pv[1], pv[0]))
    print(f"\nGBM {name}: AUC test={auc:.4f} IC95 [{np.percentile(gb,2.5):.4f}, {np.percentile(gb,97.5):.4f}] "
          f"(bootstrap Poisson por cliente R={R}, {time.time()-t1:.0f}s)")
    print(f"  pred(nulo)={pmap[-100]:.4f}  pred<=30: min={le.min():.4f} mediana={le.median():.4f} max={le.max():.4f} "
          f"(n claves <=30 con pred>pred(nulo): {(le > pmap[-100]).sum()} de {len(le)})  pred>30 min={pmap[pmap.index>3000].min():.4f}")
    # AUC si dentro de <=30 se ignora el orden del GBM (colapsar <=30 a un único valor): cuánto pierde el GBM por ruido
    s2 = pmap.copy(); s2[(s2.index >= 0) & (s2.index <= 3000)] = le.mean()
    st2 = tst.assign(s=s2.reindex(tst.index).values).groupby('s')[['pos', 'neg']].sum().sort_index()
    print(f"  mismo GBM con <=30 colapsado a un valor: AUC test={auc_hist(st2.pos, st2.neg):.4f}")
print(f"\nTiempo total {time.time()-T0:.0f}s")
