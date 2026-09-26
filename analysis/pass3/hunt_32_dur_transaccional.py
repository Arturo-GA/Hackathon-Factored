"""hunt_32: en contactos Transaccionales la duracion predice NO resolucion (AUC 0.61, hunt_31); en otras categorias no.
Caracteriza la regla: cuantiles de dur por resolved, tasa de no-resolucion por umbral, razon de tasas con IC,
y estabilidad por pais/anio/itype. Tambien wait vs resolved.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_32_dur_transaccional.py
"""
import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
q = lambda s: con.execute(s).df()
print('(1) cuantiles de dur (s) por categoria x resolved')
print(q("""SELECT cat, resolved, count(dur) n, quantile_cont(dur, [0.05,0.25,0.5,0.75,0.95]) qs, min(dur) mn, max(dur) mx
  FROM cc WHERE dur IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""").to_string())
print('(2) Transaccional: no-resolucion por umbral de duracion')
z = q("""SELECT CAST(resolved AS INT) y, dur, itype, year(ts) yr, customer_id FROM cc WHERE cat='Transaccional' AND dur IS NOT NULL""")
z['nr'] = 1 - z.y
for thr in [240, 300, 360, 420]:
    hi = z[z.dur >= thr]; lo = z[z.dur < thr]
    r1, r0 = hi.nr.mean(), lo.nr.mean()
    # IC95 de la razon de tasas (log-normal)
    se = np.sqrt((1 - r1) / (r1 * len(hi)) + (1 - r0) / (r0 * len(lo)))
    rr = r1 / r0
    print(f'dur>={thr}s: no_resuelto {r1:.4f} (n={len(hi)}, {len(hi)/len(z):.1%} de llamadas) vs <{thr}s {r0:.4f} (n={len(lo)}) '
          f'RR={rr:.2f} IC95[{rr*np.exp(-1.96*se):.2f},{rr*np.exp(1.96*se):.2f}]  captura {hi.nr.sum()/z.nr.sum():.1%} de no resueltos')
print('AUC dur -> no resuelto (Transaccional):', round(roc_auc_score(z.nr, z.dur), 4))
print('por anio:', {int(k): round(roc_auc_score(g.nr, g.dur), 4) for k, g in z.groupby('yr')})
print('por itype:', {k: round(roc_auc_score(g.nr, g.dur), 4) for k, g in z.groupby('itype')})
# dur >= 330 (max de resueltos p95?) mezcla: fraccion de no-resueltos con dur > p99 de resueltos
p99 = z[z.y == 1].dur.quantile(0.99)
print(f'p99 dur resueltos={p99:.0f}s; no resueltos por encima: {(z[z.y==0].dur > p99).mean():.3f}; resueltos por encima: {(z[z.y==1].dur > p99).mean():.3f}')
print('(3) histograma dur Transaccional por resolved (bins 60s, % columna)')
z['b'] = (z.dur // 60).astype(int).clip(upper=14)
h = pd.crosstab(z.b, z.y, normalize='columns').round(4)
h.columns = ['no_resuelto', 'resuelto']
print(h.T.to_string())
print('(4) wait vs resolved por categoria (solo Inbound)')
w = q("""SELECT cat, CAST(resolved AS INT) y, wait FROM cc WHERE wait IS NOT NULL""")
print({c: round(roc_auc_score(1 - g.y, g.wait), 4) for c, g in w.groupby('cat')})
