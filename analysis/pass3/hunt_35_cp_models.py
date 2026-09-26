"""hunt_35: objetivos a nivel reclamo con GBM (held-out 30% agrupado por cliente, IC95 bootstrap):
prioridad alta/critica, sla, repeat, rdays (R2), res_sat (R2), compensacion>0 (entre resueltos/cerrados), estado resuelto/cerrado,
tiempo a primera respuesta (R2). Features: campos del reclamo no tautologicos + atributos y agregados del cliente (cust_wide).
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_35_cp_models.py
"""
import sys, time
import duckdb
import numpy as np
import pandas as pd
sys.path.insert(0, 'analysis/pass3')
import hunt_common as hc
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
cp = con.execute("""SELECT complaint_id, customer_id, case_type, category, rchan, priority, status, sla, repeat, rdays, res_sat, compensation,
  claimed, currency, CASE WHEN affected_product_id IS NULL THEN 0 ELSE 1 END has_aff, CASE WHEN related_branch_id IS NULL THEN 0 ELSE 1 END has_branch,
  hour(ts) h, dayofweek(ts) dow, year(ts) yr, month(ts) mon, epoch(first_resp_at - ts)/3600.0 fresp_h, epoch(assigned_at - ts)/3600.0 assign_h,
  count(*) OVER (PARTITION BY customer_id ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) nprior
  FROM cp""").df()
cw = pd.read_parquet(f'{hc.CACHE}/cust_wide.parquet', columns=['customer_id', 'segment', 'credit_score', 'income_usd', 'cstatus', 'country', 'gender',
                     'occupation', 'age', 'mkt', 'tx_n', 'tx_declined', 'tx_fraud', 'cc_n', 'cc_fcr', 'cc_sent', 'sv_csat', 'pr_n', 'pr_dpd_max', 'de_n', 'cs_n'])
d = cp.merge(cw, on='customer_id', how='left')
for c in ['case_type', 'category', 'rchan', 'priority', 'status', 'currency', 'segment', 'cstatus', 'country', 'gender', 'occupation']:
    d[c] = d[c].astype('category')
BASE = ['case_type', 'category', 'rchan', 'claimed', 'currency', 'has_aff', 'has_branch', 'h', 'dow', 'yr', 'mon', 'nprior',
        'segment', 'credit_score', 'income_usd', 'cstatus', 'country', 'gender', 'occupation', 'age', 'mkt', 'tx_n', 'tx_declined', 'tx_fraud',
        'cc_n', 'cc_fcr', 'cc_sent', 'sv_csat', 'pr_n', 'pr_dpd_max', 'de_n', 'cs_n']
done = d.status.isin(['Resolved', 'Closed'])
T = {
    'prioridad_alta_critica': ('clf', d.priority.isin(['High', 'Critical']).astype(float), BASE + ['status', 'sla', 'repeat']),
    'sla_cumplido': ('clf', d.sla.astype(float), BASE + ['priority', 'status', 'repeat', 'rdays', 'fresp_h', 'assign_h']),
    'repeat': ('clf', d.repeat.astype(float), BASE + ['priority', 'status', 'sla']),
    'resuelto_o_cerrado': ('clf', done.astype(float), BASE + ['priority', 'sla', 'repeat']),
    'compensado|resuelto': ('clf', d.compensation.notna().astype(float).where(done), BASE + ['priority', 'sla', 'repeat', 'rdays']),
    'rdays': ('reg', d.rdays, BASE + ['priority', 'sla', 'repeat', 'fresp_h']),
    'res_sat': ('reg', d.res_sat, BASE + ['priority', 'sla', 'repeat', 'rdays', 'compensation']),
    'horas_primera_respuesta': ('reg', d.fresp_h, BASE + ['priority', 'sla', 'repeat']),
}
g = d.customer_id.values
for name, (kind, y, feats) in T.items():
    t = time.time()
    r = hc.fit_eval(d, feats, y, kind=kind, groups=g, top_feats=6, sample_perm=8000)
    print(hc.fmt(name, r, 'AUC' if kind == 'clf' else 'R2').split('\n')[0], f'({time.time()-t:.0f}s)', flush=True)
