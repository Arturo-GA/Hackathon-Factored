"""Verificador escéptico (reintento) de 'temporal_poisson_no_velocity'. Parte 3: seguir las anomalías pequeñas.
 a) 'tras fraude, siguiente rechazo 4.0%' (z=-2.9): ¿persiste en la 2ª/3ª tx, en la tx previa, a nivel cliente?
    placebo: 1000 subconjuntos aleatorios de ~0.1% de tx (hash) -> distribución nula del 'siguiente rechazo'
 b) exceso de intervalos <60 s entre productos del mismo cliente (148 vs 119): composición
 c) CV<1 de los intervalos por familia x ttype: ¿lo explica la ventana finita? (simulación Poisson uniforme)
 d) exceso chi² de hora por cliente (1.002): ¿hora depende de país/ttype/canal? ¿concentrado en pares cercanos?
"""
import duckdb, pandas as pd, numpy as np
from scipy.stats import binom, chi2_contingency
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

print("== a) estado de tx vecinas a un fraude ==")
r = q("""WITH s AS (SELECT fraud, fscore, hash(transaction_id) % 1000 bucket,
          lead(status,1) OVER w n1, lead(status,2) OVER w n2, lead(status,3) OVER w n3, lag(status,1) OVER w p1, lag(status,2) OVER w p2
          FROM tx WINDOW w AS (PARTITION BY product_id ORDER BY ts))
   SELECT 'fraud' grp, count(n1) n_n1, avg((n1='Declined')::INT) d_n1, count(n2) n_n2, avg((n2='Declined')::INT) d_n2,
          count(n3) n_n3, avg((n3='Declined')::INT) d_n3, count(p1) n_p1, avg((p1='Declined')::INT) d_p1,
          avg((p2='Declined')::INT) d_p2, avg((n1='Pending')::INT) pend_n1, avg((n1='Reversed')::INT) rev_n1 FROM s WHERE fraud
   UNION ALL
   SELECT 'fscore>=50', count(n1), avg((n1='Declined')::INT), count(n2), avg((n2='Declined')::INT), count(n3), avg((n3='Declined')::INT),
          count(p1), avg((p1='Declined')::INT), avg((p2='Declined')::INT), avg((n1='Pending')::INT), avg((n1='Reversed')::INT) FROM s WHERE fscore>=50
   UNION ALL
   SELECT 'todas', count(n1), avg((n1='Declined')::INT), count(n2), avg((n2='Declined')::INT), count(n3), avg((n3='Declined')::INT),
          count(p1), avg((p1='Declined')::INT), avg((p2='Declined')::INT), avg((n1='Pending')::INT), avg((n1='Reversed')::INT) FROM s""")
print(r.round(4).to_string(index=False))
pl = q("""WITH s AS (SELECT hash(transaction_id) % 1000 bucket, lead(status) OVER (PARTITION BY product_id ORDER BY ts) n1 FROM tx)
   SELECT bucket, count(n1) n, sum((n1='Declined')::INT) d FROM s GROUP BY 1""")
pl['rate'] = pl.d / pl.n
obs = 161 / 4003
print(f"placebo (1000 subconjuntos ~0.1%): tasa siguiente rechazo media {pl.rate.mean():.4f}, sd {pl.rate.std():.4f}, "
      f"fracción <= {obs:.4f}: {(pl.rate <= obs).mean():.3f}; binomial exacta P(X<=161|4003,0.0501)={binom.cdf(161, 4003, 0.0501):.4f}")
rc = q("""WITH s AS (SELECT fraud, lead(status) OVER (PARTITION BY customer_id ORDER BY ts) n1 FROM tx)
   SELECT fraud, count(n1) n, round(avg((n1='Declined')::INT),4) d FROM s GROUP BY 1""")
print("siguiente tx del CLIENTE:", rc.to_string(index=False))

print("== b) pares <60 s del mismo cliente ==")
b = q("""WITH g AS (SELECT customer_id, product_id, ttype, amount, status, ts, process_date,
          lag(product_id) OVER w pp, lag(ttype) OVER w pt, lag(amount) OVER w pa, lag(status) OVER w ps,
          date_diff('second', lag(ts) OVER w, ts) gap FROM tx WINDOW w AS (PARTITION BY customer_id ORDER BY ts))
   SELECT (pp=product_id) same_prod, pt || '->' || ttype pair, count(*) n, sum((abs(amount-pa) < 0.01)::INT) same_amount,
          sum((ps='Declined' OR status='Declined')::INT) any_decl, count(DISTINCT process_date) ndays
   FROM g WHERE gap < 60 GROUP BY ALL ORDER BY n DESC""")
print(b.head(12).to_string(index=False), "\n total", b.n.sum(), "same_amount", b.same_amount.sum())
# composición esperada bajo independencia: ttype pairs ~ producto de marginales
mt = q("SELECT ttype, count(*)::DOUBLE / (SELECT count(*) FROM tx) p FROM tx GROUP BY 1").set_index('ttype').p
print("marginales ttype:", mt.round(3).to_dict())

print("== c) CV de intervalos por familia x ttype: observado vs simulación (ventana finita) ==")
rng = np.random.default_rng(7)
T = 1097.0
share = {('cuenta', 'Deposit'): .25, ('cuenta', 'Payment'): .10, ('cuenta', 'Transfer'): .35, ('cuenta', 'Withdrawal'): .30,
         ('tarjeta', 'Purchase'): .70, ('tarjeta', 'Payment'): .15, ('prestamo', 'Payment'): .60, ('prestamo', 'Adjustment'): .30,
         ('prestamo', 'Transfer'): .10}
obs_cv = {('cuenta', 'Deposit'): .886, ('cuenta', 'Payment'): .792, ('cuenta', 'Transfer'): .926, ('cuenta', 'Withdrawal'): .907,
          ('tarjeta', 'Purchase'): .981, ('tarjeta', 'Payment'): .828, ('prestamo', 'Payment'): .972, ('prestamo', 'Adjustment'): .903,
          ('prestamo', 'Transfer'): .793}
for k, s in share.items():
    lam = 13.016 * s
    gaps = []
    for _ in range(60000):
        n = rng.poisson(lam)
        if n >= 2:
            gaps.append(np.diff(np.sort(rng.uniform(0, T, n))))
    g = np.concatenate(gaps)
    print(f"  {k}: lambda={lam:.2f} CV_sim={g.std()/g.mean():.3f} CV_obs={obs_cv[k]:.3f} media_sim={g.mean():.1f}d")

print("== d) hora vs país / ttype / canal ==")
for col in ['country', 'ttype', 'channel', 'currency']:
    t = q(f"SELECT {col} k, hour(ts) h, count(*) n FROM tx WHERE {col} IS NOT NULL GROUP BY ALL").pivot(index='k', columns='h', values='n').fillna(0)
    ch, p, dof, _ = chi2_contingency(t.values)
    V = np.sqrt(ch / (t.values.sum() * (min(t.shape) - 1)))
    print(f"  hora x {col}: V={V:.4f} chi2/dof={ch/dof:.2f} p={p:.3g}")
# pares del mismo producto (muestra 20% productos): P(misma hora) por distancia temporal
pr_ = q("""WITH s AS (SELECT product_id, ts, hour(ts) h FROM tx WHERE hash(product_id) % 5 = 0)
   SELECT CASE WHEN d < 1 THEN 'a<1d' WHEN d < 7 THEN 'b<7d' WHEN d < 30 THEN 'c<30d' WHEN d < 180 THEN 'd<180d' ELSE 'e>=180d' END dist,
          count(*) pairs, avg((h1=h2)::INT) p_same_hour
   FROM (SELECT a.h h1, b.h h2, abs(date_diff('second', a.ts, b.ts))/86400.0 d FROM s a JOIN s b
         ON a.product_id = b.product_id AND a.ts < b.ts) GROUP BY 1 ORDER BY 1""")
pr_['ratio_vs_1/24'] = (pr_.p_same_hour * 24).round(4)
print(pr_.to_string(index=False))
