"""Verificación independiente (reintento) de fraud_etiqueta_sin_semantica.
Parte A: un único GROUP BY sobre tx (+pr +cu) a una tabla de celdas pequeña; todas las marginales salen de ahí.
Mide: tasa de fraude por ttype/status/channel/ptype/segment/code/country con IC Wilson, RR, chi2, V de Cramér;
conteo de fraude 'sin pérdida' (Deposit/Adjustment/Declined) vs lo esperado por azar; fraude con fscore>30 por tipo;
fraude 'con pérdida' (débitos aprobados) según la propia definición del hallazgo."""
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2_contingency
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

cells = con.execute("""
SELECT t.ttype, t.status, coalesce(t.code,'NULL') code, t.channel, coalesce(p.ptype,'?') ptype, coalesce(c.segment,'?') segment,
       coalesce(t.country,'?') country,
       CASE WHEN t.fscore IS NULL THEN 'null' WHEN t.fscore<=30 THEN '<=30' WHEN t.fscore<50 THEN '(30,50)' ELSE '>=50' END fsb,
       t.fraud, count(*) n
FROM tx t LEFT JOIN pr p ON t.product_id=p.product_id LEFT JOIN cu c ON t.customer_id=c.customer_id
GROUP BY ALL""").df()
cells['f'] = np.where(cells.fraud, cells.n, 0)
print(f"celdas={len(cells)}")
N, F = cells.n.sum(), cells.f.sum(); base = F / N
print(f"Total tx={N:,}  fraudes={F:,}  tasa base={1e3*base:.3f} por mil\n")

def wilson(k, n, z=1.96):
    p = k / n; den = 1 + z*z/n; c = (p + z*z/(2*n)) / den
    h = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return c - h, c + h

def marg(keys, label, sub=None, show=True):
    d = cells if sub is None else cells[sub]
    b = d.f.sum() / d.n.sum()
    g = d.groupby(keys, dropna=False)[['n', 'f']].sum().reset_index()
    g['rate_pm'] = 1e3*g.f/g.n
    lo, hi = wilson(g.f.values, g.n.values); g['lo_pm'] = 1e3*lo; g['hi_pm'] = 1e3*hi
    g['rr'] = (g.f/g.n)/b
    ct = np.vstack([g.f.values, (g.n-g.f).values]).T
    chi2, p, dof, _ = chi2_contingency(ct)
    v = np.sqrt(chi2/ct.sum())
    big = g[g.n >= 20000]
    if show:
        print(f"== {label}: chi2={chi2:.1f} gl={dof} p={p:.3g} V={v:.5f}  RR(n>=20k) [{big.rr.min():.3f}, {big.rr.max():.3f}]  tasa‰(n>=20k) [{big.rate_pm.min():.3f}, {big.rate_pm.max():.3f}]")
        print(g.round(3).to_string(index=False)); print()
    return g

marg('ttype', 'Por tipo')
marg('status', 'Por estado')
marg(['ttype', 'status'], 'Tipo x estado')
marg('channel', 'Por canal')
marg('ptype', 'Por tipo de producto')
marg('segment', 'Por segmento')
marg('country', 'Por país de la tx')
marg('code', 'Por código (solo Declined)', sub=(cells.status == 'Declined'))

# --- Fraude 'sin pérdida' según el hallazgo
dep_adj = cells.ttype.isin(['Deposit', 'Adjustment'])
decl = cells.status == 'Declined'
grp = dep_adj | decl
f_grp = cells.f[grp].sum(); n_grp = cells.n[grp].sum()
print("== Fraude en Deposit/Adjustment o Declined ==")
print(f"fraude Deposit+Adjustment={cells.f[dep_adj].sum()}  fraude Declined={cells.f[decl].sum()}  solapamiento={cells.f[dep_adj & decl].sum()}")
print(f"unión={f_grp} de {F} fraudes = {100*f_grp/F:.2f}%   peso del grupo en todas las tx = {100*n_grp/N:.2f}% (n={n_grp:,})")
r1 = f_grp/n_grp; r0 = (F-f_grp)/(N-n_grp); se = np.sqrt(1/f_grp - 1/n_grp + 1/(F-f_grp) - 1/(N-n_grp))
print(f"tasa grupo={1e3*r1:.3f}‰  resto={1e3*r0:.3f}‰  RR={r1/r0:.3f} IC95=[{np.exp(np.log(r1/r0)-1.96*se):.3f}, {np.exp(np.log(r1/r0)+1.96*se):.3f}]")
debit = cells.ttype.isin(['Purchase', 'Withdrawal', 'Transfer', 'Payment'])
appr = cells.status == 'Approved'
f_loss = cells.f[debit & appr].sum()
print(f"fraude 'con pérdida' (Purchase/Withdrawal/Transfer/Payment Approved) = {f_loss} ({100*f_loss/F:.2f}%)  -> NO 'con pérdida' = {F-f_loss} ({100*(F-f_loss)/F:.2f}%)")
print(f"  de ellos: débitos Pending={cells.f[debit & (cells.status=='Pending')].sum()}  Reversed={cells.f[debit & (cells.status=='Reversed')].sum()}  Declined={cells.f[debit & decl].sum()}")
print(f"  Deposit/Adjustment por estado: " + str(cells[dep_adj & cells.fraud].groupby('status').n.sum().to_dict()))
print()

# --- fscore por tipo: ¿el score se comporta igual en créditos/ajustes que en débitos?
print("== fscore por tipo y etiqueta ==")
fs = cells.groupby(['ttype', 'fsb', 'fraud']).n.sum().unstack(['fraud']).fillna(0)
fs.columns = ['leg', 'fraud']
fs = fs.reset_index()
piv = fs.pivot(index='ttype', columns='fsb', values=['fraud', 'leg']).fillna(0).astype(int)
print(piv.to_string()); print()
out = []
for tt, d in fs.groupby('ttype'):
    d = d.set_index('fsb')
    f_gt30 = d.loc[[x for x in ['(30,50)', '>=50'] if x in d.index], 'fraud'].sum()
    l_gt30 = d.loc[[x for x in ['(30,50)', '>=50'] if x in d.index], 'leg'].sum()
    f_ge50 = d.loc['>=50', 'fraud'] if '>=50' in d.index else 0
    l_ge50 = d.loc['>=50', 'leg'] if '>=50' in d.index else 0
    f_tot = d.fraud.sum(); f_scored = d.fraud.sum() - (d.loc['null', 'fraud'] if 'null' in d.index else 0)
    out.append(dict(ttype=tt, fraudes=int(f_tot), f_con_score=int(f_scored), f_gt30=int(f_gt30), prec_gt30=f_gt30/(f_gt30+l_gt30),
                    f_ge50=int(f_ge50), prec_ge50=f_ge50/(f_ge50+l_ge50) if f_ge50+l_ge50 else np.nan,
                    recall_ge50_scored=f_ge50/f_scored, pct_null_fraude=1-f_scored/f_tot))
print(pd.DataFrame(out).round(3).to_string(index=False))
