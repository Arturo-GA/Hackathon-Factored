"""Verificador escéptico de 'temporal_poisson_no_velocity'.
1) universo: ¿Poisson(13) sobre qué productos? (Active vs con tx; ceros) ; media por ptype ; GOF chi2 vs Poisson
2) ¿la tasa depende de la antigüedad del producto (opened)? -> tx antes de apertura
3) ráfagas en datos COMPLETOS vs esperado analítico
4) control positivo: ¿el test var_obs/var_binomial detecta heterogeneidad cuando existe? (share Purchase, share país del cliente)
5) canal vs ttype / ptype (si canal depende del producto, el ratio digital debería >1)
6) fraude: productos con >=2 fraudes obs vs esperado; pstatus de productos con fraude; Declined|prev Declined en completo
"""
import duckdb, pandas as pd, numpy as np
from scipy.stats import poisson, chi2
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

print("== 1. universo de productos ==")
print(q("""WITH a AS (SELECT product_id, count(*) n FROM tx GROUP BY 1)
 SELECT p.pstatus, count(*) prods, count(a.n) with_tx, avg(coalesce(a.n,0)) mean_n_all, avg(a.n) mean_n_tx
 FROM pr p LEFT JOIN a USING(product_id) GROUP BY 1 ORDER BY 1""").to_string(index=False))
h = q("""WITH a AS (SELECT product_id, count(*) n FROM tx GROUP BY 1) SELECT n, count(*) k FROM a GROUP BY 1 ORDER BY 1""")
N = h.k.sum(); lam = (h.n*h.k).sum()/N
exp = N*poisson.pmf(h.n, lam)
# agrupar colas
obs_t = h.k.values; ex_t = exp
m = ex_t >= 5
chi = (((obs_t[m]-ex_t[m])**2)/ex_t[m]).sum()
print(f"productos con tx={N} lam={lam:.3f} chi2={chi:.1f} df={m.sum()-2} p={1-chi2.cdf(chi, m.sum()-2):.3g}  esperados con 0 tx={400000*poisson.pmf(0,lam):.2f}")
print("max |obs-exp|/exp en bins con exp>=100:", np.round(np.max(np.abs(obs_t[ex_t>=100]-ex_t[ex_t>=100])/ex_t[ex_t>=100]),4))
print(q("""WITH a AS (SELECT product_id, count(*) n FROM tx GROUP BY 1)
 SELECT p.ptype, count(*) prods, round(avg(n),3) mean, round(var_samp(n)/avg(n),3) disp FROM a JOIN pr p USING(product_id) GROUP BY 1 ORDER BY 1""").to_string(index=False))

print("== 2. tasa vs antigüedad del producto ==")
print(q("""WITH a AS (SELECT product_id, count(*) n, avg((ts::DATE < p.opened)::INT) pre_open_share FROM tx JOIN pr p USING(product_id) GROUP BY 1)
 SELECT year(p.opened) yr_open, count(*) prods, round(avg(n),3) mean_n, round(avg(pre_open_share),3) share_tx_before_open
 FROM a JOIN pr p USING(product_id) GROUP BY 1 ORDER BY 1""").to_string(index=False))

print("== 3. ráfagas datos completos ==")
g = q("""WITH g AS (SELECT product_id, date_diff('second', lag(ts) OVER (PARTITION BY product_id ORDER BY ts), ts) gap,
   count(*) OVER (PARTITION BY product_id) n FROM tx)
 SELECT count(gap) ngaps, sum((gap=0)::INT) same_sec, sum((gap<60)::INT) lt60, sum((gap<3600)::INT) lt1h, sum((gap<86400)::INT) lt1d,
   stddev(gap)/avg(gap) cv FROM g""")
print(g.to_string(index=False))
T = (pd.Timestamp('2026-06-17')-pd.Timestamp('2023-06-17')).total_seconds()
nn = h.n.values; kk = h.k.values
for s, col in [(60,'lt60'),(3600,'lt1h'),(86400,'lt1d')]:
    # esperado: n puntos uniformes en T -> n-1 gaps, P(gap<s) ≈ 1-(1-s/T)^n
    e = (kk*(nn-1)*(1-(1-s/T)**nn)).sum()
    print(f"  gaps<{s}s obs={int(g[col][0])} esperado_uniforme={e:.1f} ratio={g[col][0]/e:.2f}")
# mismo cliente (entre productos)
gc = q("""WITH g AS (SELECT customer_id, date_diff('second', lag(ts) OVER (PARTITION BY customer_id ORDER BY ts), ts) gap FROM tx)
 SELECT count(gap) ngaps, sum((gap<60)::INT) lt60, sum((gap<3600)::INT) lt1h, sum((gap=0)::INT) same_sec FROM g""")
print("cliente:", gc.to_string(index=False))

print("== 4. control positivo del test de heterogeneidad por cliente ==")
c = q("""SELECT t.customer_id, count(*) n, sum((ttype='Purchase')::INT) purch, sum((t.country=cu.country)::INT) home,
   sum((channel IN ('App','Web'))::INT) dig, sum((channel='ATM')::INT) atm, sum((status='Declined')::INT) decl,
   sum((amount_usd IS NULL)::INT) usdnull, sum((currency='USD')::INT) usd
  FROM tx t JOIN cu USING(customer_id) GROUP BY 1""")
for k in ['purch','home','dig','atm','decl','usdnull','usd']:
    p = c[k].sum()/c.n.sum(); x = c[c.n >= 10]
    print(f"  {k:8s} p={p:.4f} var_obs/var_bin={((x[k]-x.n*p)**2).mean()/(x.n*p*(1-p)).mean():.3f}")

print("== 5. canal vs ttype / ptype ==")
ct = q("SELECT ttype, channel, count(*) n FROM tx GROUP BY ALL").pivot(index='ttype', columns='channel', values='n').fillna(0)
print((ct.div(ct.sum(1), axis=0)).round(3))
from scipy.stats import chi2_contingency
def V(t):
    ch = chi2_contingency(t.values)[0]; n = t.values.sum(); return np.sqrt(ch/(n*(min(t.shape)-1)))
print("V(ttype,channel)=", round(V(ct),3))
cp = q("SELECT p.ptype, channel, count(*) n FROM tx JOIN pr p USING(product_id) GROUP BY ALL").pivot(index='ptype', columns='channel', values='n').fillna(0)
print("V(ptype,channel)=", round(V(cp),3))

print("== 6. fraude ==")
fp = q("SELECT product_id, count(*) n, sum(fraud::INT) fr FROM tx GROUP BY 1")
pf = fp.fr.sum()/fp.n.sum(); lamp = fp.n*pf
print("productos >=1 fraude obs", (fp.fr>=1).sum(), "exp", round((1-poisson.pmf(0,lamp)).sum(),1),
      "| >=2 obs", (fp.fr>=2).sum(), "exp", round((1-poisson.cdf(1,lamp)).sum(),1))
print(q("""SELECT p.pstatus, count(DISTINCT product_id) prods FROM tx JOIN pr p USING(product_id) WHERE fraud GROUP BY 1""").to_string(index=False))
print(q("""WITH s AS (SELECT status, lag(status) OVER (PARTITION BY product_id ORDER BY ts) ps, fraud, lag(fraud) OVER (PARTITION BY product_id ORDER BY ts) pf FROM tx)
 SELECT ps, count(*) n, round(avg((status='Declined')::INT),4) p_decl, round(avg(fraud::INT)*1000,3) fraud_per_mil FROM s WHERE ps IS NOT NULL GROUP BY 1 ORDER BY 1""").to_string(index=False))
print(q("""WITH s AS (SELECT fraud, lag(fraud) OVER (PARTITION BY product_id ORDER BY ts) pf, date_diff('hour', lag(ts) OVER (PARTITION BY product_id ORDER BY ts), ts) gh FROM tx)
 SELECT pf, count(*) n, round(avg(fraud::INT)*1000,3) fraud_per_mil, median(gh)/24.0 med_gap_days FROM s WHERE pf IS NOT NULL GROUP BY 1""").to_string(index=False))
# ¿el último tx de productos con fraude ocurre justo después del fraude (bloqueo implícito)?
print(q("""WITH s AS (SELECT product_id, ts, fraud, row_number() OVER (PARTITION BY product_id ORDER BY ts DESC) rdesc FROM tx)
 SELECT fraud, count(*) n, round(avg((rdesc=1)::INT),4) share_is_last_tx FROM s GROUP BY 1""").to_string(index=False))
