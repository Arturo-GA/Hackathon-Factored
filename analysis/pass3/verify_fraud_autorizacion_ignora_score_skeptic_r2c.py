"""Verificador escéptico (reintento, parte c): calibración por simulación de la 'caída de Declined tras fraude'.
Familia de 21 pruebas (producto: posteriores d=1..5, anteriores d=1..3, 5 ventanas temporales; cliente: posteriores d=1..5, anteriores d=1..3).
Se compara el p mínimo observado con el de 2,000 conjuntos de 'pseudo-fraudes' (tx legítimas al azar del mismo tamaño)."""
import sys; sys.path.insert(0, 'analysis/pass3')
import numpy as np, pandas as pd
from scipy.stats import norm
from fraud_00_common import connect, q
con = connect()

# candidatos: todo el fraude + 10% de legítimas
con.execute("""CREATE TEMP TABLE w AS SELECT transaction_id, product_id, customer_id, ts, fraud, (status='Declined')::INT dcl,
  lead(status='Declined',1) OVER wp p1, lead(status='Declined',2) OVER wp p2, lead(status='Declined',3) OVER wp p3,
  lead(status='Declined',4) OVER wp p4, lead(status='Declined',5) OVER wp p5,
  lag(status='Declined',1) OVER wp pm1, lag(status='Declined',2) OVER wp pm2, lag(status='Declined',3) OVER wp pm3,
  lead(status='Declined',1) OVER wc c1, lead(status='Declined',2) OVER wc c2, lead(status='Declined',3) OVER wc c3,
  lead(status='Declined',4) OVER wc c4, lead(status='Declined',5) OVER wc c5,
  lag(status='Declined',1) OVER wc cm1, lag(status='Declined',2) OVER wc cm2, lag(status='Declined',3) OVER wc cm3
  FROM tx WINDOW wp AS (PARTITION BY product_id ORDER BY ts, transaction_id), wc AS (PARTITION BY customer_id ORDER BY ts, transaction_id)""")
con.execute("CREATE TEMP TABLE cand AS SELECT * FROM w WHERE fraud OR hash(transaction_id) % 10 = 0")
win = q(con, """SELECT a.transaction_id,
  count(*) FILTER (WHERE b.ts < a.ts + INTERVAL 1 DAY) n_w1, sum(b.dcl) FILTER (WHERE b.ts < a.ts + INTERVAL 1 DAY) d_w1,
  count(*) FILTER (WHERE b.ts >= a.ts + INTERVAL 1 DAY AND b.ts < a.ts + INTERVAL 7 DAY) n_w2, sum(b.dcl) FILTER (WHERE b.ts >= a.ts + INTERVAL 1 DAY AND b.ts < a.ts + INTERVAL 7 DAY) d_w2,
  count(*) FILTER (WHERE b.ts >= a.ts + INTERVAL 7 DAY AND b.ts < a.ts + INTERVAL 30 DAY) n_w3, sum(b.dcl) FILTER (WHERE b.ts >= a.ts + INTERVAL 7 DAY AND b.ts < a.ts + INTERVAL 30 DAY) d_w3,
  count(*) FILTER (WHERE b.ts >= a.ts + INTERVAL 30 DAY AND b.ts < a.ts + INTERVAL 90 DAY) n_w4, sum(b.dcl) FILTER (WHERE b.ts >= a.ts + INTERVAL 30 DAY AND b.ts < a.ts + INTERVAL 90 DAY) d_w4,
  count(*) FILTER (WHERE b.ts >= a.ts + INTERVAL 90 DAY) n_w5, sum(b.dcl) FILTER (WHERE b.ts >= a.ts + INTERVAL 90 DAY) d_w5
  FROM cand a JOIN w b ON b.product_id=a.product_id AND (b.ts > a.ts OR (b.ts = a.ts AND b.transaction_id > a.transaction_id)) GROUP BY 1""")
c = q(con, "SELECT * EXCLUDE (product_id, customer_id, ts) FROM cand").merge(win, on='transaction_id', how='left')
c = c.fillna({k: 0 for k in win.columns if k != 'transaction_id'})
print(f'candidatos={len(c):,} fraude={int(c.fraud.sum()):,}')
lead_cols = ['p1', 'p2', 'p3', 'p4', 'p5', 'pm1', 'pm2', 'pm3', 'c1', 'c2', 'c3', 'c4', 'c5', 'cm1', 'cm2', 'cm3']
N = {}; D = {}
for k in lead_cols:
    v = c[k].astype('float64'); N[k] = v.notna().values.astype(np.int64); D[k] = v.fillna(0).values.astype(np.int64)
for i in range(1, 6):
    N[f'w{i}'] = c[f'n_w{i}'].values.astype(np.int64); D[f'w{i}'] = c[f'd_w{i}'].values.astype(np.int64)
tests = list(N)
leg = ~c.fraud.values
base = {k: D[k][leg].sum()/N[k][leg].sum() for k in tests}

def family(mask):
    out = {}
    for k in tests:
        n = N[k][mask].sum(); d = D[k][mask].sum(); p0 = base[k]
        z = (d - n*p0)/np.sqrt(n*p0*(1-p0)); out[k] = (d/n, n, z, 2*norm.sf(abs(z)))
    return out

obs = family(c.fraud.values)
print(pd.DataFrame({k: dict(pct_fraude=round(100*v[0], 2), n=v[1], pct_base=round(100*base[k], 2), z=round(v[2], 2), p=round(v[3], 4)) for k, v in obs.items()}).T.to_string())
pmin_obs = min(v[3] for v in obs.values())
# simulación: pseudo-fraudes = legítimas al azar (mismo n)
nf = int(c.fraud.sum()); legidx = np.where(leg)[0]; rng = np.random.default_rng(11); pmins = []; zmins = []
for _ in range(2000):
    m = np.zeros(len(c), bool); m[rng.choice(legidx, nf, replace=False)] = True
    f = family(m); pmins.append(min(v[3] for v in f.values())); zmins.append(min(v[2] for v in f.values()))
pmins = np.array(pmins)
print(f'\np mínimo observado en la familia de {len(tests)} pruebas = {pmin_obs:.4f}')
print(f'P(p mínimo <= observado | pseudo-fraudes al azar) = {np.mean(pmins <= pmin_obs):.3f}  (p ajustado por la familia)')
print(f'percentiles del p mínimo simulado: 5%={np.percentile(pmins,5):.4f} 50%={np.percentile(pmins,50):.4f}')
