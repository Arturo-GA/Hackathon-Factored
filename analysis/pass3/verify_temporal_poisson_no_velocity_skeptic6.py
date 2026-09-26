"""Verificador escéptico (reintento) de 'temporal_poisson_no_velocity'. Parte 5: reproducir cifras restantes con datos completos.
razones varianza observada/binomial por cliente; clientes con >=2 fraudes vs Poisson; CV y cuantiles normalizados de intervalos;
ráfagas por producto; % de fraudes que siguen transaccionando vs esperado 1-1/E[n]."""
import duckdb, pandas as pd, numpy as np
from scipy.stats import poisson
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
c = q("""SELECT customer_id, count(*) n, sum((dayofweek(process_date) IN (0,6))::INT) wk, sum((hour(ts - INTERVAL 6 HOUR) < 6)::INT) night,
   sum((status='Declined')::INT) decl, sum(fraud::INT) fr, sum((fscore>=50)::INT) fs50, sum((fscore>30)::INT) fs30,
   sum((channel IN ('App','Web'))::INT) dig FROM tx GROUP BY 1""")
x = c[c.n >= 10]
print("clientes", len(c), "con >=10 tx", len(x))
for k in ['wk', 'night', 'decl', 'fr', 'fs50', 'fs30', 'dig']:
    p = c[k].sum() / c.n.sum()
    r = ((x[k] - x.n * p) ** 2) / (x.n * p * (1 - p))
    print(f"  {k:6s} p={p:.4f} ratio={((x[k]-x.n*p)**2).mean()/(x.n*p*(1-p)).mean():.4f} ± {1.96*r.std()/np.sqrt(len(r)):.4f}")
lam = c.n * c.fr.sum() / c.n.sum()
print("clientes con >=2 fraudes: obs", int((c.fr >= 2).sum()), "esperado Poisson", round((1 - poisson.cdf(1, lam)).sum(), 1),
      "| >=1 obs", int((c.fr >= 1).sum()), "esp", round((1 - poisson.pmf(0, lam)).sum(), 1))
g = q("""WITH g AS (SELECT date_diff('second', lag(ts) OVER (PARTITION BY product_id ORDER BY ts), ts) gap,
          count(*) OVER (PARTITION BY product_id) n FROM tx)
   SELECT count(gap) ngaps, stddev(gap)/avg(gap) cv, sum((gap=0)::INT) s0, sum((gap<60)::INT) lt60, sum((gap<3600)::INT) lt1h,
          quantile_cont(gap/86400.0 * n/1097.0, [0.1,0.25,0.5,0.75,0.9,0.99]) qz FROM g WHERE gap IS NOT NULL""")
print(f"intervalos por producto: n={int(g.ngaps[0])} CV={g.cv[0]:.3f} mismo segundo={int(g.s0[0])} <60s={int(g.lt60[0])} "
      f"({g.lt60[0]/g.ngaps[0]*100:.4f}%) <1h={int(g.lt1h[0])} ({g.lt1h[0]/g.ngaps[0]*100:.3f}%)")
print("  cuantiles normalizados obs:", np.round(g.qz[0], 3), " exp(1):", np.round([-np.log(1-p) for p in [0.1,0.25,0.5,0.75,0.9,0.99]], 3))
f = q("""WITH s AS (SELECT fraud, lead(ts) OVER (PARTITION BY product_id ORDER BY ts) nts FROM tx)
   SELECT fraud, count(*) n, avg((nts IS NOT NULL)::INT) share_with_next FROM s GROUP BY 1""")
print(f.to_string(index=False), " esperado sin efecto: 1-1/13.016 =", round(1 - 1/13.016, 4))
