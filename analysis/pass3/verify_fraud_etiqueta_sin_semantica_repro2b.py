"""Verificación independiente (parte B) de fraud_etiqueta_sin_semantica:
1) AUC held-out (split por cliente 70/30) de modelos de tasas por celda con atributos de tx/producto/cliente,
   IC95 por bootstrap de Poisson agrupado por cliente. Si la etiqueta es azar entre tipos/estados -> AUC≈0.50.
2) Código 14 en todos los estados (¿el 1.33‰ en Declined es ruido?).
3) ¿Se puede saber la dirección de un Adjustment/Transfer/Payment? (signo, tcat, canal, ptype)."""
import duckdb, numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from scipy.stats import chi2_contingency
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

TRAIN = "(abs(hash(t.customer_id || 'v2')) % 10) < 7"
base_sql = """FROM tx t LEFT JOIN pr p ON t.product_id=p.product_id LEFT JOIN cu c ON t.customer_id=c.customer_id"""
feats = {
    'ttype': ['t.ttype'],
    'status': ['t.status'],
    'ttype_x_status': ['t.ttype', 't.status'],
    'ttype_x_status_x_channel_x_code': ['t.ttype', 't.status', 't.channel', "coalesce(t.code,'NULL')"],
    'todo_cat (tipo,estado,canal,código,ptype,segmento,país)': ['t.ttype', 't.status', 't.channel', "coalesce(t.code,'NULL')",
                                                             "coalesce(p.ptype,'?')", "coalesce(c.segment,'?')", "coalesce(t.country,'?')"],
}
# Conjunto de prueba: todos los fraudes + 300k no-fraudes muestreados de clientes de prueba (con todas las columnas de celda)
cols_all = sorted({e for v in feats.values() for e in v})
alias = {e: f"k{i}" for i, e in enumerate(cols_all)}
sel = ", ".join(f"{e} AS {alias[e]}" for e in cols_all)
test = con.execute(f"""SELECT t.customer_id, t.fraud::INT y, {sel} {base_sql} WHERE NOT ({TRAIN}) AND t.fraud""").df()
neg = con.execute(f"""SELECT * FROM (SELECT t.customer_id, t.fraud::INT y, {sel} {base_sql} WHERE NOT ({TRAIN}) AND NOT t.fraud)
                      USING SAMPLE reservoir(300000 ROWS) REPEATABLE (11)""").df()
test = pd.concat([test, neg], ignore_index=True)
ntrain = con.execute(f"SELECT count(*) n, sum(t.fraud::int) f {base_sql} WHERE {TRAIN}").fetchone()
print(f"train: n={ntrain[0]:,} fraudes={ntrain[1]:,} | test: fraudes={int(test.y.sum())} no-fraude muestreados={int((1-test.y).sum())}  clientes test={test.customer_id.nunique():,}")
cust_codes, cust_idx = np.unique(test.customer_id.values, return_inverse=True)
rng = np.random.default_rng(2026)
W = rng.poisson(1.0, size=(300, len(cust_codes))).astype(np.float32)

for name, exprs in feats.items():
    ks = [alias[e] for e in exprs]
    g = con.execute(f"SELECT {', '.join(f'{e} AS {alias[e]}' for e in exprs)}, count(*) n, sum(t.fraud::int) f {base_sql} WHERE {TRAIN} GROUP BY ALL").df()
    prior = g.f.sum()/g.n.sum(); k = 500.0
    g['s'] = (g.f + k*prior)/(g.n + k)
    d = test.merge(g[ks + ['s']], on=ks, how='left')
    d['s'] = d.s.fillna(prior)
    auc = roc_auc_score(d.y, d.s)
    boots = [roc_auc_score(d.y, d.s, sample_weight=W[b][cust_idx]) for b in range(W.shape[0])]
    print(f"AUC held-out {name:60s} celdas_train={len(g):6d}  AUC={auc:.4f}  IC95=[{np.percentile(boots,2.5):.4f}, {np.percentile(boots,97.5):.4f}]")
print()

# 2) Código 14 en todos los estados no aprobados y Approved
print("== Fraude por código dentro de cada estado ==")
d = con.execute("""SELECT status, coalesce(code,'NULL') code, count(*) n, sum(fraud::int) f FROM tx GROUP BY 1,2 ORDER BY 1,2""").df()
d['rate_pm'] = (1e3*d.f/d.n).round(3)
print(d.to_string(index=False))
nd = d[d.status != 'Approved'].groupby('code')[['n', 'f']].sum()
nd['rate_pm'] = 1e3*nd.f/nd.n
ct = np.vstack([nd.f.values, (nd.n-nd.f).values]).T; chi2, p, dof, _ = chi2_contingency(ct)
print("No aprobadas (Declined+Pending+Reversed) por código:"); print(nd.round(3).to_string())
print(f"chi2={chi2:.1f} gl={dof} p={p:.3g}")
pr_ = d[d.status.isin(['Pending', 'Reversed'])].groupby('code')[['n', 'f']].sum(); pr_['rate_pm'] = 1e3*pr_.f/pr_.n
print("Solo Pending+Reversed por código (réplica fuera de Declined):"); print(pr_.round(3).to_string()); print()

# 3) Dirección de la tx: ¿hay forma de saber si Adjustment/Transfer/Payment es débito o crédito?
print("== Atributos de dirección por tipo ==")
print(con.execute("""SELECT t.ttype, count(*) n, sum((t.amount<0)::int) n_neg, round(100*avg((t.tcat IS NOT NULL)::int),1) pct_tcat,
  round(100*avg((t.merchant_name IS NOT NULL)::int),1) pct_merch, string_agg(DISTINCT t.channel, ',') canales
  FROM tx t GROUP BY 1 ORDER BY 1""").df().to_string(index=False))
print(con.execute("""SELECT t.ttype, p.ptype, count(*) n, sum(t.fraud::int) f FROM tx t JOIN pr p USING(product_id)
  WHERE t.ttype IN ('Adjustment','Payment','Deposit') GROUP BY 1,2 ORDER BY 1,3 DESC""").df().to_string(index=False))
