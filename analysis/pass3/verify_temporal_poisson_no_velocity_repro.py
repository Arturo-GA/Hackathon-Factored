"""Verificación independiente de 'temporal_poisson_no_velocity'.
1) conteo tx por producto (incluye Active con 0 tx), bondad de ajuste Poisson, por ptype, vs fecha de apertura
2) conteo producto-mes (todos los productos con tx, meses completos)
3) intervalos entre tx del mismo producto (datos completos): CV, cuantiles normalizados, ráfagas vs esperado Poisson
4) heterogeneidad por cliente (chi2 de dispersión binomial) con definiciones propias
5) fraude: agrupamiento por cliente/producto/día, secuencia tras fraude, Markov de Declined, estado del producto tras fraude
"""
import duckdb, numpy as np, pandas as pd
from scipy import stats
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

print("== 1. tx por producto ==")
d = con.execute("""WITH a AS (SELECT product_id, count(*) n FROM tx GROUP BY 1)
  SELECT p.product_id, p.ptype, p.pstatus, year(p.opened) oy, coalesce(a.n,0) n
  FROM pr p LEFT JOIN a USING(product_id)""").fetchdf()
print(d.groupby('pstatus').n.agg(['count', 'mean', 'min', 'max']))
act = d[d.pstatus == 'Active']
n = act.n.values
lam = n.mean()
print(f"Active: {len(n)} prods, con tx={int((n>0).sum())}, media={lam:.3f}, var={n.var(ddof=1):.3f}, disp={n.var(ddof=1)/lam:.4f}, min={n.min()}, max={n.max()}")
se = np.sqrt(2/(len(n)-1))
print(f"  SE disp ~{se:.4f}; z={(n.var(ddof=1)/lam-1)/se:.2f}")
# chi2 de bondad de ajuste Poisson(lam) con colas agrupadas
obs = np.bincount(n, minlength=60)
k = np.arange(len(obs))
exp = stats.poisson.pmf(k, lam) * len(n)
lo, hi = 3, 26
o = np.r_[obs[:lo+1].sum(), obs[lo+1:hi], obs[hi:].sum()]
e = np.r_[exp[:lo+1].sum(), exp[lo+1:hi], len(n) - exp[:hi].sum()]
chi = ((o-e)**2/e).sum(); df = len(o)-2
print(f"  chi2 Poisson GOF={chi:.1f} df={df} p={stats.chi2.sf(chi, df):.3g}; esperado 0 tx={exp[0]:.2f} obs={obs[0]}; esperado >=33 = {len(n)*stats.poisson.sf(32, lam):.2f}")
print(act.groupby('ptype').n.agg(n_prod='count', mean='mean', var=lambda x: x.var(ddof=1)).assign(disp=lambda t: t['var']/t['mean']).round(3))
print("media tx por año de apertura (Active):")
print(act.groupby(pd.cut(act.oy, [0, 2015, 2019, 2022, 2023, 2024, 2025, 2027])).n.agg(['count', 'mean']).round(3))

print("\n== 2. conteo producto-mes (meses completos jul-2023..may-2026, todos los productos con tx) ==")
print(con.execute("""WITH m AS (SELECT product_id, date_trunc('month', ts - INTERVAL 6 HOUR) mo, count(*) k FROM tx
     WHERE ts - INTERVAL 6 HOUR >= '2023-07-01' AND ts - INTERVAL 6 HOUR < '2026-06-01' GROUP BY ALL),
  s AS (SELECT product_id, sum(k) sk, sum(k*k) sk2 FROM m GROUP BY 1),
  tot AS (SELECT (SELECT count(DISTINCT product_id) FROM tx) np, 35 nm)
  SELECT sum(sk)/(np*nm) mean_k, (sum(sk2) - sum(sk)^2/(np*nm))/(np*nm-1) var_k FROM s, tot GROUP BY np, nm""").fetchdf().assign(disp=lambda t: t.var_k/t.mean_k))

print("\n== 3. intervalos entre tx del mismo producto (datos completos) ==")
con.execute("""CREATE TEMP TABLE g AS SELECT product_id, status, fraud,
   epoch(ts) - epoch(lag(ts) OVER w) gap, count(*) OVER (PARTITION BY product_id) n,
   lag(status) OVER w prev_s
   FROM tx WINDOW w AS (PARTITION BY product_id ORDER BY ts, transaction_id)""")
r = con.execute("""SELECT count(gap) ng, avg(gap)/86400 mean_d, stddev(gap)/avg(gap) cv,
   sum((gap=0)::INT) same_sec, sum((gap<60)::INT) lt1m, sum((gap<3600)::INT) lt1h, sum((gap<86400)::INT) lt1d,
   -- esperado Poisson condicionado al n del producto en ventana T=1096 d: P(gap<t) ~ 1-(1-t/T)^n (orden uniforme)
   sum(1 - pow(1 - 60/(1096*86400.0), n)) e1m, sum(1 - pow(1 - 3600/(1096*86400.0), n)) e1h,
   sum(1 - pow(1 - 86400/(1096*86400.0), n)) e1d
   FROM g WHERE gap IS NOT NULL""").fetchdf()
print(r.T)
z = con.execute("""SELECT gap/86400.0 * (n/1096.0) z FROM g WHERE gap IS NOT NULL USING SAMPLE 300000 ROWS (reservoir, 7)""").fetchdf().z.values
print(f"gap normalizado (n/T): media={z.mean():.3f}, cv={z.std()/z.mean():.3f}")
for p in [0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99]:
    print(f"  q{p}: obs={np.quantile(z, p):.4f}  exp(1)={-np.log(1-p):.4f}")
print("P(status | status previo) mismo producto:")
t = con.execute("SELECT prev_s, status, count(*) c FROM g WHERE prev_s IS NOT NULL GROUP BY ALL").fetchdf().pivot(index='prev_s', columns='status', values='c')
print(t.div(t.sum(1), axis=0).round(4), "\nn filas:", t.sum(1).to_dict())

print("\n== 4. heterogeneidad por cliente ==")
c = con.execute("""SELECT customer_id, count(*) n,
  sum((isodow(ts - INTERVAL 6 HOUR) >= 6)::INT) wk,
  sum((hour(ts - INTERVAL 6 HOUR) BETWEEN 0 AND 5)::INT) night,
  sum((status='Declined')::INT) decl, sum((status='Reversed')::INT) rev, sum(fraud::INT) fr,
  sum((fscore>=50)::INT) fs50, sum((channel IN ('App','Web'))::INT) dig, sum((ttype='Purchase')::INT) purch,
  sum((amount_usd IS NULL)::INT) usdnull
  FROM tx GROUP BY 1""").fetchdf()
x = c[c.n >= 10]
print("clientes", len(c), "con >=10 tx", len(x))
for kk in ['wk', 'night', 'decl', 'rev', 'fr', 'fs50', 'dig', 'purch', 'usdnull']:
    p = c[kk].sum()/c.n.sum()
    e = x.n*p
    ratio = ((x[kk]-e)**2).sum()/(e*(1-p)).sum()
    chi = (((x[kk]-e)**2)/(e*(1-p))).sum(); dfc = len(x)-1
    print(f"  {kk:8s} p={p:.4f} var_obs/var_bin={ratio:.3f}  chi2/df={chi/dfc:.3f} (z={(chi-dfc)/np.sqrt(2*dfc):.1f})")
print("fraudes por cliente (todos):", c.fr.value_counts().sort_index().to_dict())
lam_c = c.n * c.fr.sum()/c.n.sum()
print("esperado Poisson:", {kk: round(float(stats.poisson.pmf(kk, lam_c).sum()), 1) for kk in range(4)},
      ">=2:", round(float(stats.poisson.sf(1, lam_c).sum()), 1))

print("\n== 5. fraude en secuencia de producto ==")
print(con.execute("""WITH s AS (SELECT product_id, ts, fraud, status,
    lead(ts) OVER w nts, lead(status) OVER w ns, lead(fraud) OVER w nf
    FROM tx WINDOW w AS (PARTITION BY product_id ORDER BY ts, transaction_id))
  SELECT fraud, count(*) n, sum((nts IS NOT NULL)::INT) with_next,
   median(epoch(nts)-epoch(ts))/86400 med_days_next, avg((ns='Declined')::INT) next_decl, avg(nf::INT) next_fraud,
   sum(nf::INT) n_next_fraud
  FROM s GROUP BY 1""").fetchdf().round(5).to_string(index=False))
print("productos con fraude por pstatus:")
print(con.execute("""SELECT p.pstatus, count(*) FROM (SELECT DISTINCT product_id FROM tx WHERE fraud) f JOIN pr p USING(product_id) GROUP BY 1""").fetchall())
print("tx posteriores al último fraude del producto:")
print(con.execute("""WITH lf AS (SELECT product_id, max(ts) lts FROM tx WHERE fraud GROUP BY 1)
  SELECT count(DISTINCT lf.product_id) prods, avg(cnt) mean_after, avg((cnt>0)::INT) share_with_after FROM lf
  JOIN (SELECT lf.product_id, count(t.ts) cnt FROM lf LEFT JOIN tx t ON t.product_id=lf.product_id AND t.ts>lf.lts GROUP BY 1) q USING(product_id)""").fetchdf())
print("fraudes por día: dispersión (Poisson => 1)")
print(con.execute("""WITH dd AS (SELECT process_date, sum(fraud::INT) f, count(*) n FROM tx GROUP BY 1)
  SELECT count(*) ndays, avg(f) mean_f, var_samp(f) var_f, var_samp(f)/avg(f) disp, corr(f, n) corr_f_n FROM dd""").fetchdf())
print("tx por día de la semana (hora local = UTC-6) y dispersión diaria del total:")
print(con.execute("""SELECT isodow(ts - INTERVAL 6 HOUR) dow, count(*) n, count(*)/sum(count(*)) OVER () AS shr FROM tx GROUP BY 1 ORDER BY 1""").fetchdf().round(4).to_string(index=False))
print(con.execute("""WITH dd AS (SELECT process_date, count(*) n FROM tx GROUP BY 1)
  SELECT isodow(process_date)>=6 wkend, count(*) ndays, avg(n) mean_n, var_samp(n)/avg(n) disp FROM dd GROUP BY 1""").fetchdf())
# exceso de gaps cortos: ¿se explica por la modulación semanal? esperado bajo intensidad común por día de semana
w = con.execute("""SELECT isodow(ts - INTERVAL 6 HOUR) dow, count(*) n FROM tx GROUP BY 1""").fetchdf()
sh = w.set_index('dow').n / w.n.sum()
rel = sh / (1/7)  # intensidad relativa por día
print("intensidad relativa por dow:", rel.round(3).to_dict(), " E[rel^2] (factor de exceso de gaps cortos) =", round(float((sh*rel).sum()), 3))
print("fraude diario condicionado al volumen (binomial => 1):")
print(con.execute("""WITH dd AS (SELECT process_date, sum(fraud::INT) f, count(*) n FROM tx GROUP BY 1),
  p AS (SELECT sum(f)/sum(n) p FROM dd)
  SELECT sum((f-n*p)^2)/sum(n*p*(1-p)) ratio FROM dd, p""").fetchdf())
