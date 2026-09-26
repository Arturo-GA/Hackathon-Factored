"""hunt_04: barrido supervisado de objetivos a nivel cliente con GBM (held-out 30%, IC95 bootstrap).
Para cada objetivo se excluyen las columnas tautologicas (la misma fuente/derivadas).
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_04_customer_models.py [objetivo ...]
"""
import sys, time
import numpy as np
import pandas as pd
sys.path.insert(0, 'analysis/pass3')
from hunt_common import load_cust, fit_eval, fmt

d = load_cust()
ALL = [c for c in d.columns if c not in ('customer_id',)]


def feats_excl(*prefixes, extra=()):
    return [c for c in ALL if not c.startswith(prefixes) and c not in extra]


multi_ovr = lambda col: {v: (d[col] == v).astype(float).where(d[col].notna()) for v in d[col].cat.categories}

T = {}
T['cstatus_not_active'] = ('clf', (d.cstatus != 'Active').astype(float), feats_excl('cstatus'))
T['cstatus_closed_or_inactive'] = ('clf', d.cstatus.isin(['Closed', 'Inactive']).astype(float), feats_excl('cstatus'))
T['cstatus_suspended'] = ('clf', (d.cstatus == 'Suspended').astype(float), feats_excl('cstatus'))
T['mkt'] = ('clf', d.mkt, feats_excl('mkt'))
T['credit_score'] = ('reg', d.credit_score, feats_excl('credit_score'))
T['income_usd'] = ('reg', d.income_usd, feats_excl('income_usd'))
T['log_income_usd'] = ('reg', np.log1p(d.income_usd), feats_excl('income_usd'))
T['age'] = ('reg', d.age, feats_excl('age'))
T['has_complaint'] = ('clf', d.cp_n.notna().astype(float), feats_excl('cp_', 'has_cp'))
T['repeat_complainer'] = ('clf', d.cp_repeat_any, feats_excl('cp_repeat', 'has_cp'))
T['n_contacts'] = ('reg', d.cc_n, feats_excl('cc_', 'sv_', 'has_cc', 'has_sv'))
T['fcr_mean'] = ('reg', d.cc_fcr, feats_excl('cc_fcr', 'cc_followup', 'sv_', 'has_sv'))
T['csat_mean'] = ('reg', d.sv_csat, feats_excl('sv_', 'has_sv'))
T['csat_mean_no_cc'] = ('reg', d.sv_csat, feats_excl('sv_', 'has_sv', 'cc_', 'has_cc'))
T['fraud_victim'] = ('clf', (d.tx_fraud > 0).astype(float).where(d.tx_n.notna()),
                     feats_excl('tx_fraud', 'txr_fraud', 'tx_fscore'))
T['decline_rate'] = ('reg', d.tx_decl_rate, feats_excl('tx_declined', 'txr_declined', 'tx_decl_rate', 'tx_c0', 'tx_c1', 'tx_c5',
                                                        'txr_c0', 'txr_c1', 'txr_c5', 'tx_cnull', 'txr_cnull', 'tx_pending', 'txr_pending', 'tx_reversed', 'txr_reversed'))
T['has_tx'] = ('clf', d.tx_n.notna().astype(float), feats_excl('tx', 'has_tx', 'cc_per_tx', 'pr_with_lasttx'))
T['n_tx'] = ('reg', d.tx_n, feats_excl('tx', 'has_tx', 'cc_per_tx', 'pr_with_lasttx'))
T['dpd_pos_cust'] = ('clf', (d.pr_dpd_pos > 0).astype(float).where((d.pr_pt_1 + d.pr_pt_4 + d.pr_pt_5) > 0),
                     feats_excl('pr_dpd'))
T['has_app_any'] = ('clf', (d.pr_app_share > 0).astype(float).where(d.pr_n.notna()), feats_excl('pr_app'))
T['n_complaints'] = ('reg', d.cp_n, feats_excl('cp_', 'has_cp'))
T['cs_open_rate'] = ('reg', d.cs_open, feats_excl('cs_open', 'cs_click', 'cs_conv'))
T['cs_any_conv'] = ('clf', (d.cs_conv > 0).astype(float), feats_excl('cs_conv', 'cs_click', 'cs_open'))
T['de_error_share'] = ('reg', d.de_et_error / d.de_n, feats_excl('de_et_error'))
T['sent_mean'] = ('reg', d.cc_sent, feats_excl('cc_sent', 'cc_neg', 'sv_', 'has_sv'))
for col in ['segment', 'gender', 'occupation', 'education_level', 'marital_status', 'document_type', 'country']:
    for v, y in multi_ovr(col).items():
        T[f'{col}={v}'] = ('clf', y, feats_excl(col))

sel = sys.argv[1:]
for name, (kind, y, feats) in T.items():
    if sel and not any(name.startswith(s) for s in sel):
        continue
    t = time.time()
    r = fit_eval(d, feats, y, kind=kind, top_feats=8, sample_perm=12000)
    print(fmt(name, r, 'AUC' if kind == 'clf' else 'R2'), f"({time.time()-t:.0f}s)", flush=True)
