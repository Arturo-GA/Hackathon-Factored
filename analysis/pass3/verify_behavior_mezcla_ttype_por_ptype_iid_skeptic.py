"""Verificador escéptico: behavior_mezcla_ttype_por_ptype_iid (parte 1).
(a) cobertura del join tx->pr y dueño del producto; (b) tabla ptype x ttype completa (soporte cerrado);
(c) pesos observados vs declarados con IC; (d) ¿los pesos son 'fijos' o varían por país/año/segmento/pstatus/canal?"""
import warnings; warnings.filterwarnings("ignore")
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2_contingency
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

print("== (a) cobertura join y dueño ==")
print(q("""SELECT count(*) n_tx, count(p.product_id) n_join, count(*)-count(p.product_id) sin_producto,
   sum((t.product_id IS NULL)::INT) pid_nulo, sum((p.customer_id = t.customer_id)::INT) mismo_duenio,
   sum((p.customer_id <> t.customer_id)::INT) otro_duenio
   FROM tx t LEFT JOIN pr p USING(product_id)"""))

print("== (b) ptype x ttype ==")
ct = q("SELECT coalesce(p.ptype,'<SIN PR>') ptype, t.ttype, count(*) n FROM tx t LEFT JOIN pr p USING(product_id) GROUP BY 1,2")
pv = ct.pivot(index='ptype', columns='ttype', values='n').fillna(0).astype(int)
print(pv)
pct = pv.div(pv.sum(1), axis=0) * 100
print(pct.round(2))
print("productos por ptype:\n", q("SELECT ptype, count(*) n, sum((pstatus='Active')::INT) act FROM pr GROUP BY 1 ORDER BY 1"))

decl = {
    'cuenta': {'Deposit': 25, 'Payment': 10, 'Transfer': 35, 'Withdrawal': 30},
    'tarjeta': {'Purchase': 70, 'Payment': 15, 'Withdrawal': 15},
    'otro': {'Payment': 60, 'Adjustment': 30, 'Transfer': 10},
}
def fam(pt):
    s = pt.lower()
    if 'cuenta' in s: return 'cuenta'
    if 'tarjeta' in s: return 'tarjeta'
    return 'otro'
print("== (c) desvío máximo de pesos vs declarados (pp) y z ==")
rows = []
for pt in pv.index:
    if pt == '<SIN PR>': continue
    n = pv.loc[pt].sum(); d = decl[fam(pt)]
    for tt in pv.columns:
        obs = pv.loc[pt, tt] / n * 100; exp = d.get(tt, 0)
        se = np.sqrt(max(exp, 1e-9) / 100 * (1 - exp / 100) / n) * 100 if exp > 0 else np.nan
        rows.append((pt, tt, n, round(obs, 3), exp, round(obs - exp, 3), round((obs - exp) / se, 2) if exp > 0 else np.nan))
r = pd.DataFrame(rows, columns=['ptype', 'ttype', 'n', 'obs%', 'decl%', 'dif_pp', 'z'])
print(r[r['decl%'] > 0].to_string(index=False))
print("max |dif| pp:", r['dif_pp'].abs().max(), " max|z|:", r['z'].abs().max())
# chi2 de bondad de ajuste por ptype contra pesos declarados
from scipy.stats import chisquare
for pt in pv.index:
    if pt == '<SIN PR>': continue
    d = decl[fam(pt)]; cols = list(d.keys())
    obs = pv.loc[pt, cols].values; n = obs.sum()
    exp = np.array([d[c] for c in cols]) / 100 * n
    print(f"{pt:25s} n={n:8d} GOF chi2={chisquare(obs, exp).statistic:8.2f} p={chisquare(obs, exp).pvalue:.3g}")

print("== (d) ¿pesos 'fijos'? V de Cramér ttype ~ X dentro de ptype ==")
def cramer(tab):
    tab = tab[(tab.sum(1) > 0)]; tab = tab.loc[:, tab.sum(0) > 0]
    if min(tab.shape) < 2: return np.nan, np.nan
    chi2, p, dof, _ = chi2_contingency(tab.values)
    return np.sqrt(chi2 / tab.values.sum() / (min(tab.shape) - 1)), p
dims = {
    'pais_tx': "t.country", 'anio': "year(t.ts)::VARCHAR", 'mes': "month(t.ts)::VARCHAR", 'hora': "hour(t.ts)::VARCHAR",
    'dow': "dayofweek(t.ts)::VARCHAR", 'moneda': "t.currency", 'pstatus': "p.pstatus", 'status_tx': "t.status",
    'opening_channel': "p.opening_channel", 'segmento': "c.segment", 'pais_cli': "c.country", 'cstatus': "c.cstatus",
    'anio_apertura': "year(p.opened)::VARCHAR",
}
out = []
for name, expr in dims.items():
    d = q(f"""SELECT p.ptype, {expr} x, t.ttype, count(*) n FROM tx t JOIN pr p USING(product_id)
             LEFT JOIN cu c ON c.customer_id = p.customer_id GROUP BY 1,2,3""")
    for pt, g in d.groupby('ptype'):
        tab = g.pivot_table(index='x', columns='ttype', values='n', aggfunc='sum').fillna(0)
        V, p = cramer(tab)
        # max desvío en pp de cualquier nivel con n>=2000
        tabn = tab[tab.sum(1) >= 2000]
        share = tabn.div(tabn.sum(1), axis=0) * 100
        glob = tab.sum(0) / tab.values.sum() * 100
        mx = (share - glob).abs().values.max() if len(share) else np.nan
        out.append((name, pt, int(tab.values.sum()), tab.shape[0], round(V, 4), p, round(mx, 2)))
o = pd.DataFrame(out, columns=['dim', 'ptype', 'n', 'niveles', 'V', 'p', 'max_desvio_pp(n>=2000)'])
print(o.to_string(index=False))
print("V máx:", o.V.max(), "  #p<0.001:", (o.p < 0.001).sum(), "de", len(o))
