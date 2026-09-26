"""H10: sobre-dispersion de rechazos por cliente/producto/comercio/sucursal vs binomial; process_date rule check."""
import duckdb, numpy as np, pandas as pd
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
rng = np.random.default_rng(0)
print(q("""select country, avg(case when process_date = cast(ts - interval 6 hour as date) then 1 else 0 end) regla, count(*) n from tx group by 1""").to_string())
for key in ['customer_id','product_id','merchant_name','branch_id','city']:
  for st in ['Declined','Reversed','Pending']:
    df = q(f"select {key} k, count(*) n, sum(case when status='{st}' then 1 else 0 end) x from tx where {key} is not null group by 1")
    p = df.x.sum()/df.n.sum()
    # dispersion: Pearson chi2 / df
    exp = df.n*p
    chi = ((df.x-exp)**2/(exp*(1-p))).sum()/ (len(df)-1)
    # simulacion binomial
    sims=[]
    for _ in range(20):
        xs = rng.binomial(df.n.values, p)
        sims.append((((xs-exp)**2/(exp*(1-p))).sum()/(len(df)-1)))
    # top 1% vs binomial
    big = df[df.n>=30]
    rate = big.x/big.n
    simrate = rng.binomial(big.n.values, p)/big.n.values
    print(f"{key:14s} {st:9s} grupos={len(df):7d} p={p:.4f} dispersion={chi:.3f} (sim {np.mean(sims):.3f}±{np.std(sims):.3f}) "
          f"n>=30:{len(big)} p99 real={np.quantile(rate,0.99) if len(big) else np.nan:.3f} sim={np.quantile(simrate,0.99) if len(big) else np.nan:.3f} max real={rate.max() if len(big) else np.nan:.3f} sim={simrate.max() if len(big) else np.nan:.3f}")
