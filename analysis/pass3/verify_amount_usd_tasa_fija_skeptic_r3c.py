# Verificador escéptico (r3c): ¿los nulos de amount_usd en ARS/COP son MCAR?
import duckdb, time, numpy as np, pandas as pd
from scipy.stats import chi2_contingency
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
def q(s, show=True):
    df = con.execute(s).df()
    if show: print(df.to_string(), '\n', flush=True)
    return df

base = """from tx t join pr p using(product_id) join cu c on c.customer_id=t.customer_id
          where t.currency in ('ARS','COP')"""
feats = {
 'currency':'t.currency', 'status':'t.status', 'ttype':'t.ttype', 'channel':'t.channel', 'fraud':'t.fraud',
 'fscore_null':'(t.fscore is null)', 'fscore_ge50':"coalesce(t.fscore>=50, false)", 'code':"coalesce(t.code,'NULL')",
 'merchant_null':'(t.merchant_name is null)', 'lat_null':'(t.lat is null)', 'tcat_null':'(t.tcat is null)',
 'country_eq':"(t.country = c.country)", 'year':'year(t.ts)', 'quarter':"strftime(t.ts,'%Y-Q')||quarter(t.ts)",
 'dow':'dayofweek(t.ts)', 'hour':'hour(t.ts)', 'amount_dec':"least(9, floor((t.amount/(case t.currency when 'ARS' then 350 else 4000 end))/1000))::int",
 'ptype':'p.ptype', 'pstatus':'p.pstatus', 'segment':'c.segment', 'cstatus':'c.cstatus', 'lag_days':"least(5, datediff('day', t.ts::date, t.process_date))",
}
rows = []
for name, expr in feats.items():
    d = q(f"select {expr} k, count(*) n, sum((t.amount_usd is null)::int) nul {base} group by 1", show=False)
    d = d[d.n >= 500]
    d['rate'] = d.nul / d.n
    tab = np.vstack([d.nul.values, (d.n - d.nul).values]).T
    chi2, pval, dof, _ = chi2_contingency(tab)
    V = np.sqrt(chi2 / tab.sum())  # 2 columnas -> V = sqrt(chi2/n)
    rows.append(dict(var=name, niveles=len(d), rate_min=round(d.rate.min(),4), rate_max=round(d.rate.max(),4),
                     ratio_max_min=round(d.rate.max()/d.rate.min(),3), V=round(V,4), p=float(f"{pval:.3g}"),
                     n_min=int(d.n.min())))
print("== 9. tasa de nulos (ARS/COP) por variable ==")
print(pd.DataFrame(rows).to_string(), '\n', flush=True)
print(f"[t={time.time()-t0:.0f}s]")

print("== 10. sobredispersion por cliente y por producto (>=10 tx) ==")
for key in ['customer_id', 'product_id']:
    d = q(f"select {key}, count(*) n, avg((amount_usd is null)::int) r from tx where currency in ('ARS','COP') group by 1 having count(*)>=10", show=False)
    p = (d.r*d.n).sum()/d.n.sum()
    print(key, "grupos", len(d), "var_obs", round(d.r.var(),6), "var_binomial_esperada", round((p*(1-p)/d.n).mean(),6),
          "ratio", round(d.r.var()/(p*(1-p)/d.n).mean(),3))
print()
print("== 11. dependencia secuencial: P(nulo | tx anterior del mismo producto nula) ==")
q("""with s as (select product_id, ts, (amount_usd is null) nul, lag(amount_usd is null) over (partition by product_id order by ts, transaction_id) prev
     from tx where currency in ('ARS','COP'))
     select prev, count(*) n, round(avg(nul::int),5) p_nul from s where prev is not null group by 1 order by 1""")
print(f"[t={time.time()-t0:.0f}s]")

print("== 12. AUC held-out (agrupado por cliente) para predecir nulo con todas las variables ==")
d = q(f"""select t.customer_id, (t.amount_usd is null)::int y, t.currency, t.status, t.ttype, t.channel, t.fraud::int fraud,
   coalesce(t.fscore,-1) fscore, coalesce(t.code,'NULL') code, (t.merchant_name is null)::int mnull, (t.lat is null)::int latnull,
   (t.country = c.country)::int same_country, epoch(t.ts)/86400 dnum, hour(t.ts) hr, dayofweek(t.ts) dow,
   ln(t.amount/(case t.currency when 'ARS' then 350 else 4000 end)) lamt, datediff('day', t.ts::date, t.process_date) lagd,
   p.ptype, p.pstatus, c.segment, c.credit_score, c.income
   {base} using sample 300000 rows""", show=False)
print("muestra", len(d), "tasa nulos", round(d.y.mean(),4), flush=True)
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
cat_cols = ['currency','status','ttype','channel','code','ptype','pstatus','segment']
for cc in cat_cols: d[cc] = d[cc].astype('category').cat.codes
X = d.drop(columns=['customer_id','y']).astype(float).fillna(-1)
y = d.y.values
gss = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=0)
tr, te = next(gss.split(X, y, groups=d.customer_id))
m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200,
     categorical_features=[X.columns.get_loc(c) for c in cat_cols], random_state=0)
m.fit(X.iloc[tr], y[tr])
pr_ = m.predict_proba(X.iloc[te])[:,1]
auc = roc_auc_score(y[te], pr_)
rng = np.random.default_rng(0)
# bootstrap agrupado por cliente
gte = d.customer_id.values[te]
ug, inv = np.unique(gte, return_inverse=True)
boots = []
idx_by_g = pd.Series(np.arange(len(te))).groupby(inv).apply(np.array).values
for b in range(200):
    samp = rng.integers(0, len(ug), len(ug))
    ii = np.concatenate([idx_by_g[s] for s in samp])
    boots.append(roc_auc_score(y[te][ii], pr_[ii]))
print("HGB AUC held-out", round(auc,4), "IC95", np.round(np.percentile(boots,[2.5,97.5]),4))
Xs = (X - X.iloc[tr].mean())/X.iloc[tr].std().replace(0,1)
lr = LogisticRegression(max_iter=500).fit(Xs.iloc[tr], y[tr])
print("LogReg AUC held-out", round(roc_auc_score(y[te], lr.predict_proba(Xs.iloc[te])[:,1]),4))
print(f"[t={time.time()-t0:.0f}s]")
