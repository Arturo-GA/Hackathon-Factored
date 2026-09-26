import duckdb, numpy as np
from sklearn.metrics import roc_auc_score
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
df = con.execute("""select t.customer_id, t.fraud::int y,
   sqrt(pow(t.lat-(case cu.country when 'Argentina' then -34.6037 when 'Colombia' then 4.711 else 0 end),2)
      + pow(t.lon-(case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 else 0 end),2)) d
   from tx t join cu using(customer_id) where t.lat is not null and t.lon is not null and (t.fraud or random()<0.25)""").df()
print(len(df), df.y.sum(), 'auc', round(roc_auc_score(df.y, df.d),4))
rng = np.random.default_rng(0)
cust = df.customer_id.unique(); idx = df.groupby('customer_id').indices
aucs=[]
for _ in range(300):
    s = rng.choice(cust, len(cust), replace=True)
    ii = np.concatenate([idx[c] for c in s])
    aucs.append(roc_auc_score(df.y.values[ii], df.d.values[ii]))
print('bootstrap(customer) 95% CI', np.round(np.percentile(aucs,[2.5,97.5]),4))
