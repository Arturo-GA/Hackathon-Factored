"""Escéptico r2, H: ¿'pesos fijos' por tx o propensión propia de producto/cliente? Índice de dispersión multinomial
(obs/esperado; 1 = iid) por ptype y ttype para productos y clientes con >=5 tx de ese ptype; y mezcla de la 1a tx vs resto."""
import warnings; warnings.filterwarnings("ignore")
import duckdb, numpy as np, pandas as pd
pd.set_option("display.width", 230)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
FAM = "CASE WHEN p.ptype LIKE 'Cuenta%' THEN 'Cuenta' WHEN p.ptype LIKE 'Tarjeta%' THEN 'Tarjeta' ELSE 'Otro' END"
for unit in ['t.product_id', 't.customer_id']:
    d = q(f"""WITH c AS (SELECT {unit} u, {FAM} fam, t.ttype, count(*) k FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2,3),
        n AS (SELECT u, fam, sum(k) n FROM c GROUP BY 1,2 HAVING sum(k) >= 5),
        g AS (SELECT fam, ttype, sum(k)*1.0/sum(sum(k)) OVER (PARTITION BY fam) pr FROM c GROUP BY 1,2),
        x AS (SELECT n.u, n.fam, n.n, g.ttype, g.pr, coalesce(c.k,0) k FROM n JOIN g ON n.fam=g.fam LEFT JOIN c ON c.u=n.u AND c.fam=n.fam AND c.ttype=g.ttype)
      SELECT fam, ttype, count(*) unidades, avg(n) n_medio, sum(power(k - n*pr, 2)) / sum(n*pr*(1-pr)) disp FROM x GROUP BY 1,2 ORDER BY 1,2""")
    d['se_aprox'] = np.sqrt(2 / d.unidades)
    print(f"== dispersión por {unit} (1 = multinomial iid; se~sqrt(2/unidades)) ==")
    print(d.round(4).to_string(index=False))
d = q(f"""WITH z AS (SELECT {FAM} fam, t.ttype, row_number() OVER (PARTITION BY t.product_id ORDER BY t.ts, t.transaction_id) rk
          FROM tx t JOIN pr p USING(product_id))
        SELECT fam, (rk=1) primera, ttype, count(*) n FROM z GROUP BY ALL""")
pv = d.pivot_table(index=['fam', 'primera'], columns='ttype', values='n', aggfunc='sum').fillna(0)
print("== mezcla % 1a tx del producto vs resto ==")
print((pv.div(pv.sum(1), axis=0) * 100).round(2).assign(n=pv.sum(1).astype(int)).to_string())
