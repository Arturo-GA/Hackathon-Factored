"""(a) ¿La secuencia de ttype es iid dado ptype? (V de Cramér prev->next dentro de cada ptype)
(b) ¿Rechazo/fraude/pending se agrupan en el tiempo dentro del producto/cliente? P(X|prev X) vs P(X)."""
from behavior_common import connect, q
import numpy as np
from scipy.stats import chi2_contingency
con = connect()
m = q(con, """WITH s AS (SELECT p.ptype, t.ttype, lag(t.ttype) OVER (PARTITION BY t.product_id ORDER BY t.ts) prev FROM tx t JOIN pr p USING(product_id))
  SELECT ptype, prev, ttype, count(*) n FROM s WHERE prev IS NOT NULL GROUP BY 1,2,3""")
for pt, g in m.groupby('ptype'):
    pv = g.pivot(index='prev', columns='ttype', values='n').fillna(0).values
    chi2, p, dof, _ = chi2_contingency(pv)
    V = np.sqrt(chi2/pv.sum()/(min(pv.shape)-1))
    print(f"{pt:22s} n={int(pv.sum()):8d} V={V:.4f} p={p:.3g}")
print(q(con, "SELECT status, count(*) n, count(*)*1.0/sum(count(*)) over () pct FROM tx GROUP BY 1"))
for part in ['product_id','customer_id']:
    print(f"== {part} ==")
    print(q(con, f"""WITH s AS (SELECT status, fraud, lag(status) OVER (PARTITION BY {part} ORDER BY ts) ps, lag(fraud) OVER (PARTITION BY {part} ORDER BY ts) pf FROM tx)
      SELECT ps, count(*) n, avg((status='Declined')::INT) p_decl, avg((status='Pending')::INT) p_pend, avg((status='Reversed')::INT) p_rev, avg(fraud::INT) p_fraud
      FROM s WHERE ps IS NOT NULL GROUP BY 1 ORDER BY 1"""))
    print(q(con, f"""WITH s AS (SELECT fraud, lag(fraud) OVER (PARTITION BY {part} ORDER BY ts) pf FROM tx)
      SELECT pf, count(*) n, avg(fraud::INT) p_fraud FROM s WHERE pf IS NOT NULL GROUP BY 1"""))
# sobre-dispersión de rechazos por cliente: varianza observada vs binomial
d = q(con, "SELECT customer_id, count(*) n, sum((status='Declined')::INT) k FROM tx GROUP BY 1")
p = d.k.sum()/d.n.sum()
obs = ((d.k - d.n*p)**2).sum(); exp_ = (d.n*p*(1-p)).sum()
print("rechazos: p=%.4f dispersión obs/esperada binomial=%.3f" % (p, obs/exp_))
d = q(con, "SELECT customer_id, count(*) n, sum(fraud::INT) k FROM tx GROUP BY 1")
p = d.k.sum()/d.n.sum(); obs = ((d.k - d.n*p)**2).sum(); exp_ = (d.n*p*(1-p)).sum()
print("fraude: p=%.5f dispersión=%.3f" % (p, obs/exp_))
