"""Escéptico r2, D2: nivel cliente con TODOS los clientes; test ttype_next ⟂ ttype_prev | (ptype_prev, ptype_next, mismo_producto, gap)
y comparación con orden barajado dentro del cliente. Reporta contribuciones máximas al chi2 (celdas prev->next con mayor desvío)."""
import warnings; warnings.filterwarnings("ignore")
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2 as chi2dist, chi2_contingency
pd.set_option("display.width", 230)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
res = {}
for lab, order in [('obs', 't.ts, t.transaction_id'), ('shuf', "hash(t.transaction_id || 'r2b')")]:
    parts = []
    for b in range(8):
        parts.append(q(f"""WITH z AS (SELECT p.ptype, t.ttype, t.product_id, t.ts,
                    lag(p.ptype) OVER w pptype, lag(t.ttype) OVER w prev, lag(t.product_id) OVER w pprod, lag(t.ts) OVER w pts
                  FROM tx t JOIN pr p USING(product_id) WHERE hash(t.customer_id) % 8 = {b}
                  WINDOW w AS (PARTITION BY t.customer_id ORDER BY {order}))
                SELECT pptype, prev, ptype, ttype, (pprod = product_id) same,
                  CASE WHEN abs(epoch(ts-pts))<86400 THEN 'a<1d' WHEN abs(epoch(ts-pts))<7*86400 THEN 'b<7d' ELSE 'c>=7d' END gb, count(*) n
                FROM z WHERE prev IS NOT NULL GROUP BY ALL"""))
    res[lab] = pd.concat(parts).groupby(['pptype', 'prev', 'ptype', 'ttype', 'same', 'gb']).n.sum().reset_index()
for lab, d in res.items():
    N = d.n.sum()
    for strat in [['pptype', 'ptype'], ['pptype', 'ptype', 'same'], ['pptype', 'ptype', 'same', 'gb']]:
        c2s, dofs, cells = 0.0, 0, []
        for key, h in d.groupby(strat):
            tab = h.pivot_table(index='prev', columns='ttype', values='n', aggfunc='sum').fillna(0)
            tab = tab.loc[tab.sum(1) > 0, tab.sum(0) > 0]
            if min(tab.shape) >= 2:
                c2, _, dof, e = chi2_contingency(tab.values, correction=False); c2s += c2; dofs += dof
                r = (tab.values - e) / np.sqrt(e)
                for i, a in enumerate(tab.index):
                    for j, c in enumerate(tab.columns):
                        cells.append((key, a, c, int(tab.values[i, j]), round(e[i, j], 1), round(r[i, j], 2), round(tab.values[i, j] / e[i, j], 3)))
        print(f"[{lab}] N={N} estratos={'+'.join(strat)}: chi2={c2s:.1f} dof={dofs} chi2/dof={c2s / dofs:.3f} p={chi2dist.sf(c2s, dofs):.3g}")
        if strat == ['pptype', 'ptype']:
            C = pd.DataFrame(cells, columns=['estrato', 'prev', 'next', 'obs', 'esp', 'resid', 'razon'])
            print("   top |resid|:"); print(C.reindex(C.resid.abs().sort_values(ascending=False).index).head(6).to_string(index=False))
            big = C[C.esp >= 1000]
            print(f"   celdas con esp>=1000: {len(big)}; razón obs/esp min={big.razon.min():.3f} max={big.razon.max():.3f}")
