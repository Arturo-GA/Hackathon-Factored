# Verificacion independiente (reintento) - Parte G: test MCAR multivariado (AUC held-out agrupado por cliente)
import duckdb, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
df = con.execute("""select t.customer_id, (t.amount_usd is null)::int y, t.currency, t.ttype, t.channel, t.status, coalesce(t.code,'NA') code,
    t.fraud::int fraud, coalesce(t.fscore,-1) fscore, (t.lat is null)::int lat_null, (t.merchant_name is null)::int mn_null,
    coalesce(t.mcat,'NA') mcat, coalesce(t.country,'NA') pais_tx, cu.segment, cu.country pais_cli, pr.ptype,
    t.amount/(case t.currency when 'ARS' then 350 else 4000 end) monto_eq, hour(t.ts) hora, dayofweek(t.ts) dow, month(t.ts) mes,
    (epoch(t.ts) - epoch(timestamp '2023-06-17'))/86400.0 dia, date_diff('day', t.ts::date, t.process_date) lag_proc
    from tx t join cu using(customer_id) join pr using(product_id)
    where t.currency in ('ARS','COP') and hash(t.customer_id) % 8 = 0""").df()
print('filas', len(df), 'tasa nulos', round(df.y.mean()*100,3), f'[{time.time()-t0:.0f}s]', flush=True)
cats = ['currency','ttype','channel','status','code','mcat','pais_tx','segment','pais_cli','ptype']
for c in cats: df[c] = df[c].astype('category').cat.codes
feats = cats + ['fraud','fscore','lat_null','mn_null','monto_eq','hora','dow','mes','dia','lag_proc']
cust = np.array(df.customer_id.unique(), dtype=object); rng = np.random.default_rng(7); rng.shuffle(cust)
test_c = set(cust[: int(len(cust)*0.3)])
te = df.customer_id.isin(test_c).values
m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, categorical_features=[feats.index(c) for c in cats], random_state=0)
m.fit(df.loc[~te, feats], df.loc[~te, 'y'])
p = m.predict_proba(df.loc[te, feats])[:, 1]; yt = df.loc[te, 'y'].values
auc = roc_auc_score(yt, p)
# bootstrap por cliente
g = df.loc[te, 'customer_id'].astype('category').cat.codes.values; ng = g.max() + 1
idx_by_g = pd.Series(np.arange(len(g))).groupby(g).apply(np.array).values
boots = []
for b in range(200):
    pick = rng.integers(0, ng, ng)
    ii = np.concatenate(idx_by_g[pick])
    boots.append(roc_auc_score(yt[ii], p[ii]))
print(f'AUC held-out (clientes) = {auc:.4f}  IC95 [{np.percentile(boots,2.5):.4f}, {np.percentile(boots,97.5):.4f}]  n_test={te.sum()}  nulos_test={yt.sum()}')
# por decil de probabilidad predicha: tasa real
dd = pd.DataFrame({'p': p, 'y': yt}); dd['dec'] = pd.qcut(dd.p.rank(method='first'), 10, labels=False)
print(dd.groupby('dec').y.mean().mul(100).round(2).to_string(), f'\n[{time.time()-t0:.0f}s]')
