"""Verificador escéptico: behavior_mezcla_ttype_por_ptype_iid (parte 3).
(e) nivel cliente cruzando productos: transiciones observadas vs orden barajado dentro del cliente (controla composición exacta);
(f) posición en la secuencia del producto (1a tx, última) y gap previo vs ttype;
(g) montos: corr consecutiva vs corr con orden barajado dentro del producto (secuencial vs efecto fijo de producto), por moneda."""
import warnings; warnings.filterwarnings("ignore")
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2_contingency
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
K = 8
print("== (e) cliente: obs vs barajado ==")
res = {}
for label, order in [('obs', 't.ts, t.transaction_id'), ('shuf', 'hash(t.transaction_id || \'x\')')]:
    parts = []
    for b in range(K):
        parts.append(q(f"""WITH z AS (SELECT p.ptype || ':' || t.ttype k, t.product_id,
            lag(p.ptype || ':' || t.ttype) OVER w pk, lag(t.product_id) OVER w pp
            FROM tx t JOIN pr p USING(product_id) WHERE hash(t.customer_id) % {K} = {b}
            WINDOW w AS (PARTITION BY t.customer_id ORDER BY {order}))
          SELECT pk, k, count(*) n, sum((pp=product_id)::INT) same_prod FROM z WHERE pk IS NOT NULL GROUP BY 1,2"""))
    res[label] = pd.concat(parts).groupby(['pk', 'k']).sum().reset_index()
o, s_ = res['obs'], res['shuf']
print("P(misma cuenta que la tx previa del cliente): obs=%.4f  barajado=%.4f" % (o.same_prod.sum() / o.n.sum(), s_.same_prod.sum() / s_.n.sum()))
M = o.merge(s_, on=['pk', 'k'], how='outer', suffixes=('_o', '_s')).fillna(0)
M['ratio'] = M.n_o / M.n_s.replace(0, np.nan)
big = M[(M.n_s >= 2000)]
print("celdas:", len(M), " con n>=2000:", len(big), " ratio obs/barajado min=%.3f max=%.3f" % (big.ratio.min(), big.ratio.max()))
print(big.sort_values('ratio').iloc[[0, 1, 2, -3, -2, -1]][['pk', 'k', 'n_o', 'n_s', 'ratio']].to_string(index=False))
tab = M[['n_o', 'n_s']].values.T; tab = tab[:, tab.sum(0) > 0]
chi2, p, dof, _ = chi2_contingency(tab)
print("V obs-vs-barajado (todas las celdas): %.4f  chi2=%.0f dof=%d p=%.3g" % (np.sqrt(chi2 / tab.sum()), chi2, dof, p))
# ejemplo de negocio: Transfer/Withdrawal en cuenta seguido de Payment en tarjeta
for a, c in [('Cuenta Ahorro:Transfer', 'Tarjeta Crédito:Payment'), ('Cuenta Ahorro:Deposit', 'Cuenta Ahorro:Withdrawal'),
             ('Tarjeta Crédito:Purchase', 'Tarjeta Crédito:Payment'), ('Cuenta Corriente:Deposit', 'Tarjeta Débito:Purchase')]:
    r = M[(M.pk == a) & (M.k == c)]
    if len(r): print(f"  {a} -> {c}: obs={int(r.n_o.iloc[0])} barajado={int(r.n_s.iloc[0])} ratio={r.ratio.iloc[0]:.3f}")

print("== (f) ttype según posición en el producto y gap previo (dentro de ptype) ==")
parts = []
for b in range(2):
    parts.append(q(f"""WITH z AS (SELECT p.ptype, t.ttype, row_number() OVER w rk, count(*) OVER (PARTITION BY t.product_id) ntx,
        epoch(t.ts - lag(t.ts) OVER w)/86400.0 g, date_diff('day', p.opened, t.ts::DATE) dop
        FROM tx t JOIN pr p USING(product_id) WHERE hash(t.product_id) % {K} = {b}
        WINDOW w AS (PARTITION BY t.product_id ORDER BY t.ts, t.transaction_id))
      SELECT ptype, CASE WHEN rk=1 THEN '1ra' WHEN rk=ntx THEN 'ultima' ELSE 'media' END pos,
        CASE WHEN g IS NULL THEN 'na' WHEN g<7 THEN 'a<7d' WHEN g<30 THEN 'b<30d' WHEN g<90 THEN 'c<90d' WHEN g<180 THEN 'd<180d' ELSE 'e>=180d' END gb,
        CASE WHEN dop<0 THEN 'antes_apertura' WHEN dop<30 THEN '<30d_apertura' ELSE '>=30d' END ob,
        ttype, count(*) n FROM z GROUP BY ALL"""))
F = pd.concat(parts).groupby(['ptype', 'pos', 'gb', 'ob', 'ttype']).n.sum().reset_index()
def cramer(tab):
    tab = tab.loc[tab.sum(axis=1) > 0, tab.sum(axis=0) > 0]
    chi2, p, dof, _ = chi2_contingency(tab.values)
    return np.sqrt(chi2 / tab.values.sum() / (min(tab.shape) - 1)), p
for dim in ['pos', 'gb', 'ob']:
    for fam, g in F.assign(fam=F.ptype.str.split().str[0]).groupby('fam'):
        tab = g.pivot_table(index=dim, columns='ttype', values='n', aggfunc='sum').fillna(0)
        V, p = cramer(tab)
        sh = tab.div(tab.sum(axis=1), axis=0) * 100
        print(f"{dim:4s} {fam:10s} V={V:.4f} p={p:.3f}  rango%% por nivel: " + "; ".join(f"{c}:{sh[c].min():.1f}-{sh[c].max():.1f}" for c in sh.columns))
print("  % tx antes de la apertura del producto:", round(F[F.ob == 'antes_apertura'].n.sum() / F.n.sum() * 100, 2))

print("== (g) montos: corr log consecutiva vs barajada dentro del producto, por moneda ==")
for label, order in [('consecutiva', 't.ts, t.transaction_id'), ('barajada', "hash(t.transaction_id || 'y')")]:
    print(label, q(f"""WITH z AS (SELECT t.currency, t.ttype, ln(abs(t.amount)+1) la, lag(ln(abs(t.amount)+1)) OVER (PARTITION BY t.product_id ORDER BY {order}) pla,
        lag(t.ttype) OVER (PARTITION BY t.product_id ORDER BY {order}) pt
        FROM tx t WHERE hash(t.product_id) % {K} = 0)
      SELECT currency, count(*) n, round(corr(la, pla),4) corr_all, round(corr(la, pla) FILTER (WHERE ttype=pt),4) corr_mismo_tipo
      FROM z WHERE pla IS NOT NULL GROUP BY 1 ORDER BY 1""").to_string(index=False))
