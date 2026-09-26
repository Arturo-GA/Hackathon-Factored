"""Brotes temporales: dispersion diaria/horaria de la tasa de rechazo vs binomial (dias de 'caida del sistema')."""
import duckdb, numpy as np, warnings
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
rng=np.random.default_rng(1)
for grain, expr in [('dia','process_date'),('hora',"date_trunc('hour', ts)"),('dia_x_pais',"process_date||country"),('dia_x_canal',"process_date||channel"),('dia_x_comercio',"process_date||coalesce(merchant_name,'-')")]:
  for st in ['Declined','Pending','Reversed']:
    df = con.execute(f"select {expr} k, count(*) n, sum(case when status='{st}' then 1 else 0 end) x from tx group by 1").fetchdf()
    p = df.x.sum()/df.n.sum(); e=df.n*p
    disp = ((df.x-e)**2/(e*(1-p))).sum()/(len(df)-1)
    sim = [(((rng.binomial(df.n.values,p)-e)**2/(e*(1-p))).sum()/(len(df)-1)) for _ in range(20)]
    big=df[df.n>=200]; r=big.x/big.n; rs=rng.binomial(big.n.values,p)/big.n.values
    print(f"{grain:15s} {st:9s} celdas={len(df):6d} dispersion={disp:.3f} sim={np.mean(sim):.3f}±{np.std(sim):.3f} max_tasa(n>=200) real={r.max():.3f} sim={rs.max():.3f}")
