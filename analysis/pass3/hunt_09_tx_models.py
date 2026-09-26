"""hunt_09: modelos a nivel TRANSACCION (GBM) sobre el historial completo de ~10k clientes muestreados (~330k tx),
con features de la tx, del historial previo del cliente/producto (ventanas), del producto y del cliente.
Objetivos: Declined, Reversed, Pending, fraude (sin fscore), codigo dentro de Declined, fscore nulo.
Held-out 30% agrupado por cliente, IC95 bootstrap.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_09_tx_models.py
"""
import sys, time
import duckdb
import numpy as np
import pandas as pd
sys.path.insert(0, 'analysis/pass3')
import hunt_common as hc

OUT = hc.CACHE
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
USD = "(t.amount / CASE t.currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END)"
t0 = time.time()
con.execute(f"""COPY (
WITH cs AS (SELECT customer_id FROM cu WHERE hash(customer_id) % 15 = 3),
t AS (SELECT t.* FROM tx t JOIN cs USING (customer_id))
SELECT t.transaction_id, t.customer_id, t.status, t.code, CAST(t.fraud AS INT) fraud, t.fscore,
 t.ttype, t.tcat, t.channel, t.mcat, t.country tcountry, t.currency, t.merchant_name, t.city tcity,
 CASE WHEN t.country = c.country THEN 0 ELSE 1 END away,
 ln(1+{USD}) lusd, CASE WHEN {USD}=round({USD}) THEN 1 ELSE 0 END amt_round,
 hour(t.ts) hr, dayofweek(t.ts) dow, day(t.ts) dom, month(t.ts) mon, year(t.ts) yr,
 date_diff('day', CAST(t.ts AS DATE), t.process_date) proc_lag,
 CASE WHEN t.branch_id IS NULL THEN 0 ELSE 1 END has_branch, CASE WHEN t.lat IS NULL THEN 0 ELSE 1 END has_latlon,
 epoch(t.ts - lag(t.ts) OVER w)/3600.0 hrs_since_prev,
 epoch(lead(t.ts) OVER w - t.ts)/3600.0 hrs_to_next_LEAK,
 lag(t.status) OVER w prev_status, lag(t.ttype) OVER w prev_ttype,
 lag(t.status) OVER wp prev_status_prod,
 count(*) FILTER (WHERE t.status='Declined') OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) prior_decl,
 count(*) OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) prior_n,
 count(*) OVER (PARTITION BY t.customer_id ORDER BY t.ts RANGE BETWEEN INTERVAL 24 HOURS PRECEDING AND CURRENT ROW) n_24h,
 count(*) OVER (PARTITION BY t.customer_id ORDER BY t.ts RANGE BETWEEN INTERVAL 7 DAYS PRECEDING AND CURRENT ROW) n_7d,
 sum({USD}) OVER (PARTITION BY t.customer_id ORDER BY t.ts RANGE BETWEEN INTERVAL 7 DAYS PRECEDING AND CURRENT ROW) usd_7d,
 {USD} / nullif(p.bal / CASE p.currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END, 0) amt_over_bal,
 {USD} / nullif(p.credit_limit / CASE p.currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END, 0) amt_over_limit,
 p.ptype, p.dpd, p.rate, CAST(p.app AS INT) papp, p.opening_channel,
 date_diff('day', p.opened, CAST(t.ts AS DATE)) days_since_open, date_diff('day', CAST(t.ts AS DATE), p.expires) days_to_exp,
 c.segment, c.credit_score, c.income / CASE c.country WHEN 'Colombia' THEN 4000.0 WHEN 'Argentina' THEN 350.0 ELSE 17.0 END income_usd,
 c.cstatus, c.gender, c.occupation, date_diff('day', c.dob, DATE '2026-06-17')/365.25 cage, CAST(c.mkt AS INT) mkt, c.country ccountry,
 date_diff('day', c.registration_date, t.ts) days_since_reg
FROM t LEFT JOIN pr p USING (product_id) LEFT JOIN cu c ON c.customer_id = t.customer_id
WINDOW w AS (PARTITION BY t.customer_id ORDER BY t.ts), wp AS (PARTITION BY t.product_id ORDER BY t.ts)
) TO '{OUT}/tx_sample_feats.parquet' (FORMAT parquet)""")
d = pd.read_parquet(f'{OUT}/tx_sample_feats.parquet')
print('sample', d.shape, d.customer_id.nunique(), f'{time.time()-t0:.0f}s', flush=True)
d['prior_decl_rate'] = d.prior_decl / d.prior_n.replace(0, np.nan)
CATS = ['ttype', 'tcat', 'channel', 'mcat', 'tcountry', 'currency', 'merchant_name', 'tcity', 'prev_status', 'prev_ttype',
        'prev_status_prod', 'ptype', 'opening_channel', 'segment', 'cstatus', 'gender', 'occupation', 'ccountry']
for c in CATS:
    d[c] = d[c].astype('category')
hc.src_of = lambda c: ('hist' if c in ('hrs_since_prev', 'prev_status', 'prev_ttype', 'prev_status_prod', 'prior_decl', 'prior_n',
                                       'prior_decl_rate', 'n_24h', 'n_7d', 'usd_7d') else
                       'prod' if c in ('amt_over_bal', 'amt_over_limit', 'ptype', 'dpd', 'rate', 'papp', 'opening_channel', 'days_since_open', 'days_to_exp') else
                       'cust' if c in ('segment', 'credit_score', 'income_usd', 'cstatus', 'gender', 'occupation', 'cage', 'mkt', 'ccountry', 'days_since_reg') else 'tx')
BASE = [c for c in d.columns if c not in ('transaction_id', 'customer_id', 'status', 'code', 'fraud', 'fscore', 'hrs_to_next_LEAK')]
g = d.customer_id.values
T = {
    'declined': ('clf', (d.status == 'Declined').astype(float), BASE + ['fscore']),
    'reversed': ('clf', (d.status == 'Reversed').astype(float), BASE + ['fscore']),
    'pending': ('clf', (d.status == 'Pending').astype(float), BASE + ['fscore']),
    'not_approved': ('clf', (d.status != 'Approved').astype(float), BASE + ['fscore']),
    'declined_with_next_gap': ('clf', (d.status == 'Declined').astype(float), BASE + ['hrs_to_next_LEAK']),
    'fraud_no_fscore': ('clf', d.fraud.astype(float), BASE),
    'fscore_null': ('clf', d.fscore.isna().astype(float), BASE),
}
dec = d.status == 'Declined'
for code in ['05', '14', '51', '54']:
    T[f'decl_code_{code}'] = ('clf', (d.code == code).astype(float).where(dec), BASE + ['fscore'])
nonapp = d.status.isin(['Pending', 'Reversed'])
T['pend_rev_has_code'] = ('clf', d.code.isin(['05', '14', '51', '54']).astype(float).where(nonapp), BASE + ['fscore'])
for name, (kind, y, feats) in T.items():
    t = time.time()
    r = hc.fit_eval(d, feats, y, kind=kind, groups=g, top_feats=8, sample_perm=15000)
    print(hc.fmt(name, r), f"({time.time()-t:.0f}s)", flush=True)
