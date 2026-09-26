"""Verificador escéptico: behavior_mezcla_ttype_por_ptype_iid (parte 2: secuencias, por cubetas para no agotar RAM).
(a) empates de ts; (b) lag-1 y lag-2 dentro de ptype (V); (c) lifts prev->next;
(d) ¿gap o monto dependen del par (prev,next)? ciclos depósito->retiro por tiempo/monto; regularidad de pagos; día del mes;
(e) nivel cliente cruzando productos: transiciones observadas vs orden barajado dentro del cliente."""
import warnings; warnings.filterwarnings("ignore")
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2_contingency
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
K = 8

def cramer(tab):
    tab = tab.loc[tab.sum(axis=1) > 0, tab.sum(axis=0) > 0]
    chi2, p, dof, _ = chi2_contingency(tab.values)
    return np.sqrt(chi2 / tab.values.sum() / (min(tab.shape) - 1)), p

print("== (a) empates de ts dentro del producto y del cliente ==")
print(q("""SELECT (SELECT count(*) FROM (SELECT product_id, ts FROM tx GROUP BY 1,2 HAVING count(*)>1)) grupos_empate_prod,
                  (SELECT count(*) FROM (SELECT customer_id, ts FROM tx GROUP BY 1,2 HAVING count(*)>1)) grupos_empate_cli""").to_string(index=False))

seq, gaps, amts = [], [], []
for b in range(K):
    base = f"""WITH z AS (SELECT p.ptype, t.ttype, t.amount, t.ts, t.product_id,
        lag(t.ttype,1) OVER w prev1, lag(t.ttype,2) OVER w prev2, lag(t.amount,1) OVER w pamt,
        epoch(t.ts - lag(t.ts,1) OVER w)/86400.0 gap_d
        FROM tx t JOIN pr p USING(product_id) WHERE hash(t.product_id) % {K} = {b}
        WINDOW w AS (PARTITION BY t.product_id ORDER BY t.ts, t.transaction_id))"""
    seq.append(q(base + " SELECT ptype, prev1, prev2, ttype, count(*) n FROM z WHERE prev1 IS NOT NULL GROUP BY ALL"))
    if b < 2:
        gaps.append(q(base + """ SELECT CASE WHEN ptype LIKE 'Cuenta%' THEN 'cuenta' WHEN ptype LIKE 'Tarjeta%' THEN 'tarjeta' ELSE 'prest/inv/seg' END fam,
            prev1, ttype, count(*) n, median(gap_d) med_gap, avg(gap_d) mean_gap, avg((gap_d<1)::INT)*100 pct_lt1d,
            avg((gap_d<0.125)::INT)*100 pct_lt3h, corr(ln(abs(amount)+1), ln(abs(pamt)+1)) corr_log,
            avg((abs(amount)=abs(pamt))::INT)*100 pct_igual FROM z WHERE prev1 IS NOT NULL GROUP BY ALL"""))
S = pd.concat(seq).groupby(['ptype', 'prev1', 'prev2', 'ttype'], dropna=False).n.sum().reset_index()
print("== (b) V de Cramér dentro de ptype: lag1 y lag2 ==")
for pt, g in S.groupby('ptype'):
    V1, p1 = cramer(g.pivot_table(index='prev1', columns='ttype', values='n', aggfunc='sum').fillna(0))
    g2 = g.dropna(subset=['prev2']); g2 = g2.assign(h=g2.prev2 + '|' + g2.prev1)
    V2, p2 = cramer(g2.pivot_table(index='h', columns='ttype', values='n', aggfunc='sum').fillna(0))
    print(f"{pt:22s} n={int(g.n.sum()):8d} V_lag1={V1:.4f} p={p1:.3f}  V_lag2={V2:.4f} p={p2:.3f}")
print("== (c) lifts prev->next dentro de ptype ==")
rows = []
for pt, g in S.groupby('ptype'):
    tab = g.pivot_table(index='prev1', columns='ttype', values='n', aggfunc='sum').fillna(0)
    exp = np.outer(tab.sum(axis=1), tab.sum(axis=0)) / tab.values.sum(); lift = tab / exp
    for a in tab.index:
        for c in tab.columns:
            rows.append((pt, a, c, int(tab.loc[a, c]), round(lift.loc[a, c], 3)))
L = pd.DataFrame(rows, columns=['ptype', 'prev', 'next', 'n', 'lift'])
print("lift min/max:", L.lift.min(), L.lift.max()); print(L.sort_values('lift').iloc[[0, 1, -2, -1]].to_string(index=False))
# log-loss: ptype-solo vs ptype+prev1+prev2 (entrenado en cubetas 0-5, evaluado en 6-7)
tr_ = pd.concat(seq[:6]).dropna(subset=['prev2']); te_ = pd.concat(seq[6:]).dropna(subset=['prev2'])
def ll(keys):
    p = tr_.groupby(keys + ['ttype']).n.sum() / tr_.groupby(keys).n.sum()
    p = p.rename('p').reset_index()
    m = te_.merge(p, on=keys + ['ttype'], how='left').fillna({'p': 1e-6})
    return -(m.n * np.log(m.p)).sum() / m.n.sum()
l0 = ll(['ptype']); l2 = ll(['ptype', 'prev1', 'prev2'])
print("log-loss held-out: ptype=%.5f  ptype+prev1+prev2=%.5f  mejora=%.5f nats (%.3f%%)" % (l0, l2, l0 - l2, (l0 - l2) / l0 * 100))

G = pd.concat(gaps)
G = G.groupby(['fam', 'prev1', 'ttype']).apply(lambda d: pd.Series({'n': d.n.sum(), 'med_gap': np.average(d.med_gap, weights=d.n),
    'pct_lt1d': np.average(d.pct_lt1d, weights=d.n), 'pct_lt3h': np.average(d.pct_lt3h, weights=d.n),
    'corr_log': np.average(d.corr_log, weights=d.n), 'pct_igual': np.average(d.pct_igual, weights=d.n)})).reset_index()
print("== (d1) gap y monto por (prev,next), cubetas 0-1 (~1/4 de los datos) ==")
print(G.round(3).to_string(index=False))

print("== (d3) regularidad de pagos (¿cuotas mensuales?) ==")
print(q("""WITH p AS (SELECT pr.ptype, epoch(t.ts - lag(t.ts) OVER (PARTITION BY t.product_id ORDER BY t.ts))/86400.0 g
     FROM tx t JOIN pr USING(product_id) WHERE t.ttype='Payment' AND pr.ptype IN ('Préstamo Personal','Préstamo Hipotecario','Tarjeta Crédito') AND hash(t.product_id)%4=0)
   SELECT ptype, count(*) n, quantile_cont(g,[0.1,0.5,0.9]) q, round(stddev(g)/avg(g),3) cv, round(avg((g BETWEEN 28 AND 32)::INT)*100,2) pct_28_32,
     round(avg((g BETWEEN 0 AND 4)::INT)*100,2) pct_0_4
   FROM p WHERE g IS NOT NULL GROUP BY 1""").to_string(index=False))
print("== (d4) día del mes (% por día) ==")
dm = q("""SELECT CASE WHEN t.ttype='Deposit' THEN 'Deposit' WHEN p.ptype LIKE 'Préstamo%' AND t.ttype='Payment' THEN 'PagoPrestamo'
   WHEN p.ptype='Tarjeta Crédito' AND t.ttype='Payment' THEN 'PagoTC' ELSE 'otro' END k, day(t.ts) d, count(*) n
   FROM tx t JOIN pr p USING(product_id) GROUP BY ALL""")
pv = dm.pivot(index='d', columns='k', values='n'); pv = pv.div(pv.sum(axis=0), axis=1) * 100
print(pv.loc[1:28].agg(['min', 'max']).round(2)); print(pv.loc[[1, 15, 16, 29, 30, 31]].round(2))
