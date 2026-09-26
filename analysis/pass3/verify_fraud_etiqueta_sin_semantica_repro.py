"""Verificación independiente: ¿la etiqueta fraud es independiente de tipo de tx, estado, canal, tipo de producto y segmento?
¿Qué fracción del fraude cae en casos 'sin pérdida' (Deposit/Adjustment/Declined)?"""
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2_contingency
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

def df(sql):
    return con.execute(sql).df()

def wilson(k, n, z=1.96):
    p = k / n; den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h

tot = df("SELECT count(*) n, sum(fraud::int) f, count(*) FILTER (WHERE fraud IS NULL) fnull FROM tx")
N, F = int(tot.n[0]), int(tot.f[0]); base = F / N
print(f"Total tx={N:,}  fraudes={F:,}  tasa={1e3*base:.3f} por mil  (fraud nulo={int(tot.fnull[0])})\n")

def table(expr, label, join='', min_n=0):
    d = df(f"""SELECT {expr}::VARCHAR v, count(*) n, sum(t.fraud::int) f,
               sum((t.fraud AND t.fscore>30)::int) f_gt30, sum((t.fraud AND t.fscore>=50)::int) f_ge50
               FROM tx t {join} GROUP BY 1 ORDER BY 1""")
    d['rate_pm'] = 1e3 * d.f / d.n
    lo, hi = zip(*[wilson(k, n) for k, n in zip(d.f, d.n)])
    d['ci_lo_pm'] = 1e3 * np.array(lo); d['ci_hi_pm'] = 1e3 * np.array(hi)
    d['rr_vs_base'] = (d.f / d.n) / base
    ct = np.vstack([d.f.values, (d.n - d.f).values]).T
    chi2, p, dof, _ = chi2_contingency(ct)
    v = np.sqrt(chi2 / (ct.sum() * (min(ct.shape) - 1)))
    dd = d[d.n >= min_n]
    print(f"== {label}  chi2={chi2:.1f} dof={dof} p={p:.3g}  V de Cramér={v:.5f}  RR rango(n>={min_n})=[{dd.rr_vs_base.min():.2f}, {dd.rr_vs_base.max():.2f}]")
    print(d.round({'rate_pm': 3, 'ci_lo_pm': 3, 'ci_hi_pm': 3, 'rr_vs_base': 3}).to_string(index=False)); print()
    return d

table("t.ttype", "Por tipo de transacción")
table("t.status", "Por estado")
table("t.channel", "Por canal")
table("p.ptype", "Por tipo de producto", join="LEFT JOIN pr p USING(product_id)")
table("c.segment", "Por segmento de cliente", join="LEFT JOIN cu c ON t.customer_id=c.customer_id")
table("t.ttype || ' | ' || t.status", "Tipo x estado (celdas)")

print("== Fraudes 'sin pérdida' (definición del hallazgo: Deposit/Adjustment o Declined) ==")
print(df("""SELECT count(*) FILTER (WHERE fraud) f_total,
  count(*) FILTER (WHERE fraud AND ttype IN ('Deposit','Adjustment')) f_dep_adj,
  count(*) FILTER (WHERE fraud AND status='Declined') f_declined,
  count(*) FILTER (WHERE fraud AND ttype IN ('Deposit','Adjustment') AND status='Declined') f_overlap,
  count(*) FILTER (WHERE fraud AND (ttype IN ('Deposit','Adjustment') OR status='Declined')) f_sin_perdida,
  count(*) FILTER (WHERE fraud AND (ttype IN ('Deposit','Adjustment') OR status<>'Approved')) f_no_aprob_o_credito,
  count(*) FILTER (WHERE fraud AND ttype IN ('Purchase','Withdrawal','Transfer','Payment') AND status='Approved') f_con_perdida
  FROM tx""").T.to_string()); print()

print("== Fraude con fscore>30 / >=50 en depósitos y ajustes ==")
print(df("""SELECT ttype, count(*) FILTER (WHERE fraud) f, count(*) FILTER (WHERE fraud AND fscore>30) f_gt30,
  count(*) FILTER (WHERE fraud AND fscore>=50) f_ge50, count(*) FILTER (WHERE NOT fraud AND fscore>30) leg_gt30,
  round(avg(fscore) FILTER (WHERE fraud),2) fscore_medio_fraude, round(avg(fscore) FILTER (WHERE NOT fraud),2) fscore_medio_leg
  FROM tx WHERE ttype IN ('Deposit','Adjustment') OR TRUE GROUP BY 1 ORDER BY 1""").to_string(index=False)); print()

print("== Signo/magnitud de monto por tipo (¿un Adjustment puede ser débito?) ==")
print(df("""SELECT ttype, count(*) n, round(min(amount),2) mn, round(max(amount),2) mx,
  sum((amount<0)::int) n_neg, sum((amount=0)::int) n_cero, round(median(amount),2) med
  FROM tx GROUP BY 1 ORDER BY 1""").to_string(index=False)); print()

print("== Subcategoría (tcat) dentro de Deposit/Adjustment: fraude ==")
print(df("""SELECT ttype, tcat, count(*) n, sum(fraud::int) f, round(1e3*avg(fraud::int),3) rate_pm
  FROM tx WHERE ttype IN ('Deposit','Adjustment') GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False)); print()

print("== fscore en fraude por grupo (¿el score 'sabe' que es depósito/rechazada?) ==")
print(df("""SELECT CASE WHEN ttype IN ('Deposit','Adjustment') THEN 'credito/ajuste' ELSE 'debito' END g,
  status, count(*) f, count(fscore) f_scored, round(avg(fscore),2) avg_fs,
  round(100*avg((fscore>30)::int),1) pct_gt30_de_scored
  FROM tx WHERE fraud GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False)); print()

# Prueba de azar: bajo independencia, ¿cuántos fraudes se esperarían en el grupo 'sin pérdida'?
d = df("""SELECT (ttype IN ('Deposit','Adjustment') OR status='Declined') g, count(*) n, sum(fraud::int) f FROM tx GROUP BY 1""")
share_tx = d.loc[d.g, 'n'].iloc[0] / d.n.sum(); share_f = d.loc[d.g, 'f'].iloc[0] / d.f.sum()
print(f"Grupo 'sin pérdida': {100*share_tx:.2f}% de las tx vs {100*share_f:.2f}% de los fraudes -> RR={share_f/share_tx:.3f}")
g = d.set_index('g')
r1 = g.loc[True, 'f'] / g.loc[True, 'n']; r0 = g.loc[False, 'f'] / g.loc[False, 'n']
se = np.sqrt(1 / g.loc[True, 'f'] - 1 / g.loc[True, 'n'] + 1 / g.loc[False, 'f'] - 1 / g.loc[False, 'n'])
print(f"Tasa sin pérdida {1e3*r1:.3f}‰ vs resto {1e3*r0:.3f}‰  RR={r1/r0:.3f} IC95=[{np.exp(np.log(r1/r0)-1.96*se):.3f}, {np.exp(np.log(r1/r0)+1.96*se):.3f}]")
