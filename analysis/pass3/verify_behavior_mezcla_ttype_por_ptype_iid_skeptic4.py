"""Verificador escéptico: behavior_mezcla_ttype_por_ptype_iid (parte 4).
(h) sobredispersión por producto y por cliente del conteo de cada ttype (¿propensión propia del producto/cliente?);
(i) día del mes: participación de Deposit vs resto de tipos (¿efecto quincena propio del depósito?)."""
import warnings; warnings.filterwarnings("ignore")
import duckdb, numpy as np, pandas as pd
pd.set_option("display.width", 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
print("== (h) índice de dispersión obs/esperado multinomial (1 = iid) ==")
for unit in ['product_id', 'customer_id']:
    d = q(f"""WITH c AS (SELECT t.{unit} u, p.ptype, t.ttype, count(*) k FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2,3),
        n AS (SELECT u, ptype, sum(k) n FROM c GROUP BY 1,2),
        g AS (SELECT ptype, ttype, sum(k)*1.0/sum(sum(k)) OVER (PARTITION BY ptype) pr FROM c GROUP BY 1,2)
      SELECT n.ptype, g.ttype, sum(power(coalesce(c.k,0) - n.n*g.pr, 2)) obs, sum(n.n*g.pr*(1-g.pr)) exp, count(*) units
      FROM n JOIN g ON n.ptype=g.ptype LEFT JOIN c ON c.u=n.u AND c.ptype=n.ptype AND c.ttype=g.ttype
      WHERE n.n >= 5 GROUP BY 1,2 ORDER BY 1,2""")
    d['disp'] = d.obs / d.exp
    print(unit, "(unidades con >=5 tx de ese ptype) disp min=%.3f max=%.3f" % (d.disp.min(), d.disp.max()))
    print(d[['ptype', 'ttype', 'units', 'disp']].round(3).to_string(index=False))
print("== (i) día del mes: % Deposit / % resto de tipos ==")
dm = q("SELECT (ttype='Deposit') dep, day(ts) d, count(*) n FROM tx GROUP BY ALL")
pv = dm.pivot(index='d', columns='dep', values='n'); pv = pv.div(pv.sum(axis=0), axis=1) * 100
r = (pv[True] / pv[False])
print("ratio días 1-31 min=%.3f max=%.3f; días 15,16,30,1 =" % (r.min(), r.max()), r.loc[[15, 16, 30, 1]].round(3).tolist())
print("% Deposit días 1-28 min/max:", pv[True].loc[1:28].min().round(2), pv[True].loc[1:28].max().round(2), "; día 30:", pv[True].loc[30].round(2))
