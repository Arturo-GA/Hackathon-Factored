"""hunt_06: barrido supervisado a nivel producto (GBM, held-out 30% agrupado por cliente, IC95 bootstrap).
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_06_product_models.py [objetivo ...]
"""
import sys, time
import numpy as np
import pandas as pd
sys.path.insert(0, 'analysis/pass3')
import hunt_common as hc
from hunt_common import fit_eval, fmt

d = pd.read_parquet(f'{hc.CACHE}/prod_wide.parquet')
CATS = ['ptype', 'pcur', 'pstatus', 'opening_channel', 'pnum_pfx', 'segment', 'cstatus', 'ccountry', 'gender', 'occupation',
        'education_level', 'marital_status']
for c in CATS:
    d[c] = d[c].astype('category')
d['ptx_decl_rate'] = d['ptx_declined'] / d['ptx_n']
ALL = [c for c in d.columns if c not in ('product_id', 'customer_id')]
hc.src_of = lambda c: ('ptx' if c.startswith('ptx_') else 'pde' if c.startswith('pde_') else 'pcc' if c.startswith('pcc_')
                       else 'pcp' if c.startswith('pcp_') else 'cust_agg' if c.startswith('cust_') else
                       'cu' if c in ('segment', 'credit_score', 'income_usd', 'cstatus', 'ccountry', 'mkt', 'cage', 'gender',
                                     'occupation', 'education_level', 'marital_status', 'c_nprod') else 'pr')
TXF = tuple(['ptx_', 'lasttx', 'cust_tx'])


def ex(*prefixes, extra=()):
    return [c for c in ALL if not c.startswith(prefixes) and c not in extra]


credit = d.ptype.isin(['Tarjeta Crédito', 'Préstamo Personal', 'Préstamo Hipotecario'])
T = {}
T['dpd_pos_credit'] = ('clf', (d.dpd > 0).astype(float).where(credit), ex('dpd'))
T['dpd_ge30_credit'] = ('clf', (d.dpd >= 30).astype(float).where(credit), ex('dpd'))
T['dpd_value_given_pos'] = ('reg', d.dpd.where(d.dpd > 0), ex('dpd'))
T['pstatus_not_active'] = ('clf', (d.pstatus != 'Active').astype(float), ex('pstatus', *TXF))
T['pstatus_blocked'] = ('clf', (d.pstatus == 'Blocked').astype(float), ex('pstatus', *TXF))
T['pstatus_closed'] = ('clf', (d.pstatus == 'Closed').astype(float), ex('pstatus', *TXF))
T['nonactive_blocked_vs_rest'] = ('clf', (d.pstatus == 'Blocked').astype(float).where(d.pstatus != 'Active'), ex('pstatus', *TXF))
T['nonactive_closed_vs_rest'] = ('clf', (d.pstatus == 'Closed').astype(float).where(d.pstatus != 'Active'), ex('pstatus', *TXF))
T['app'] = ('clf', d.app, ex('app'))
T['prod_decline_rate'] = ('reg', d.ptx_decl_rate, ex('ptx_declined', 'ptx_decl_rate', 'ptx_c', 'ptx_pending', 'ptx_reversed'))
T['prod_fraud_any'] = ('clf', (d.ptx_fraud > 0).astype(float).where(d.ptx_n.notna()), ex('ptx_fraud', 'ptx_fscore', 'cust_tx_fraud'))
T['prod_has_complaint_ref'] = ('clf', d.pcp_n.notna().astype(float), ex('pcp_'))

sel = sys.argv[1:]
groups = d['customer_id'].values
for name, (kind, y, feats) in T.items():
    if sel and not any(name.startswith(s) for s in sel):
        continue
    t = time.time()
    # submuestreo para RAM si objetivo cubre todos los productos
    m = ~pd.isna(y)
    idx = np.where(m)[0]
    if len(idx) > 250000:
        idx = np.random.default_rng(0).choice(idx, 250000, replace=False)
    dd = d.iloc[idx]
    r = fit_eval(dd, feats, y.iloc[idx], kind=kind, groups=groups[idx], top_feats=8, sample_perm=12000)
    print(fmt(name, r, 'AUC' if kind == 'clf' else 'R2'), f"({time.time()-t:.0f}s)", flush=True)
