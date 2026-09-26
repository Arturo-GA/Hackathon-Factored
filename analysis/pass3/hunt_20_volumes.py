"""hunt_20: que explica el VOLUMEN por cliente de cada fuente (de_n, de_nsess, cs_n, sv_n, cp_n, cc_n) y su sobre-dispersion vs Poisson.
GBM R2 held-out excluyendo la propia fuente (y sv para cc por ser derivada de interacciones).
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_20_volumes.py
"""
import sys, time
import numpy as np
sys.path.insert(0, 'analysis/pass3')
from hunt_common import load_cust, fit_eval, fmt

d = load_cust()
ALL = [c for c in d.columns if c != 'customer_id']
for col, excl in [('de_n', ('de_', 'has_de')), ('de_nsess', ('de_', 'has_de')), ('cs_n', ('cs_', 'has_cs')),
                  ('sv_n', ('sv_', 'has_sv')), ('cc_n', ('cc_', 'sv_', 'has_cc', 'has_sv')), ('cp_n', ('cp_', 'has_cp'))]:
    x = d[col].fillna(0)
    print(f"{col}: media={x.mean():.2f} var={x.var():.2f} var/media={x.var()/x.mean():.2f} (Poisson=1)")
    feats = [c for c in ALL if not c.startswith(excl)]
    t = time.time()
    r = fit_eval(d, feats, x, kind='reg', top_feats=6, sample_perm=10000)
    print(fmt(col, r, 'R2'), f'({time.time()-t:.0f}s)', flush=True)
# de_n vs n productos / n activos / tx
print(d[['de_n', 'de_nsess', 'pr_n', 'pr_st_active', 'tx_n', 'cc_n', 'cs_n']].corr().round(3).to_string())
# errores digitales: escalan con sesiones o con eventos?
e = d[['de_n', 'de_nsess', 'de_et_error', 'de_et_login', 'de_et_logout', 'de_et_pageview', 'de_et_click', 'de_et_purchase', 'de_et_formsubmit']].dropna()
print(e.corr().round(3)[['de_n', 'de_nsess', 'de_et_error']].to_string())
print('ratios medios por sesion:', (e[['de_et_error', 'de_et_login', 'de_et_logout', 'de_et_pageview', 'de_n']].div(e.de_nsess, axis=0)).mean().round(3).to_dict())
