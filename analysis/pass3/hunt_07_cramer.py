"""hunt_07: barrido de dependencias ocultas entre TODOS los pares de columnas categoricas (V de Cramer corregida + MI normalizada).
(a) nivel transaccion: columnas de tx + derivadas (hora, dia, mes, decil de monto, nulos) + atributos del cliente y producto (join),
    sobre muestra aleatoria de 1.2M tx (parquet en hunt_cache).
(b) nivel cliente: columnas de cu + derivadas. (c) nivel producto: columnas de pr + derivadas.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_07_cramer.py
"""
import duckdb, itertools, time
import numpy as np
import pandas as pd

OUT = 'analysis/pass3/hunt_cache'
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
USD = "(t.amount / CASE t.currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END)"

t0 = time.time()
import os
qs = con.execute(f"SELECT approx_quantile({USD.replace('t.','')}, [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9]) FROM tx").fetchone()[0]
AMTDEC = "CASE " + " ".join([f"WHEN {USD} < {q} THEN '{i}'" for i, q in enumerate(qs)]) + " ELSE '9' END"
if not os.path.exists(f'{OUT}/tx_cat_sample.parquet'):
  con.execute(f"""COPY (
SELECT t.ttype, coalesce(t.tcat,'∅') tcat, t.currency, t.channel, coalesce(t.mcat,'∅') mcat, t.country tcountry,
  coalesce(t.country_raw,'∅') country_raw, coalesce(t.city,'∅') tcity, t.status, coalesce(t.code,'∅') code,
  CAST(t.fraud AS VARCHAR) fraud, CASE WHEN t.fscore IS NULL THEN 'null' WHEN t.fscore>=50 THEN 'hi' ELSE 'lo' END fscore_b,
  coalesce(t.merchant_name,'∅') merchant, CASE WHEN t.branch_id IS NULL THEN 'no' ELSE 'yes' END has_branch,
  CASE WHEN t.lat IS NULL THEN 'no' ELSE 'yes' END has_latlon,
  CAST(hour(t.ts) AS VARCHAR) hr, CAST(dayofweek(t.ts) AS VARCHAR) dow, CAST(month(t.ts) AS VARCHAR) mon,
  CAST(year(t.ts) AS VARCHAR) yr, CAST(least(day(t.ts),31) AS VARCHAR) dom,
  CAST(least(date_diff('day', CAST(t.ts AS DATE), t.process_date), 5) AS VARCHAR) proc_lag,
  {AMTDEC} amt_dec,
  CASE WHEN {USD} = round({USD}) THEN 'round' ELSE 'frac' END amt_round,
  CASE WHEN t.amount_usd IS NULL THEN 'null' ELSE 'val' END amt_usd_null,
  c.segment, c.gender, coalesce(c.occupation,'∅') occupation, c.cstatus, c.country ccountry, CAST(c.mkt AS VARCHAR) mkt,
  coalesce(c.education_level,'∅') education, coalesce(c.marital_status,'∅') marital,
  CAST(floor(date_diff('day', c.dob, DATE '2026-06-17')/3652.5) AS VARCHAR) age_dec,
  p.ptype, CAST(p.app AS VARCHAR) papp, p.opening_channel, CAST(year(p.opened) AS VARCHAR) popen_yr,
  CASE WHEN t.country = c.country THEN 'home' ELSE 'away' END home
FROM (SELECT * FROM tx USING SAMPLE 800000 ROWS) t
LEFT JOIN cu c USING (customer_id) LEFT JOIN pr p USING (product_id)
) TO '{OUT}/tx_cat_sample.parquet' (FORMAT parquet)""")
print('sample built', time.time() - t0, flush=True)


def cramers_v_corr(ct):
    n = ct.sum()
    r, k = ct.shape
    if r < 2 or k < 2:
        return np.nan, np.nan
    e = np.outer(ct.sum(1), ct.sum(0)) / n
    chi2 = ((ct - e) ** 2 / np.where(e > 0, e, 1)).sum()
    phi2 = chi2 / n
    phi2c = max(0, phi2 - (k - 1) * (r - 1) / (n - 1))
    rc = r - (r - 1) ** 2 / (n - 1)
    kc = k - (k - 1) ** 2 / (n - 1)
    v = np.sqrt(phi2c / max(1e-12, min(kc - 1, rc - 1)))
    # MI normalizada (por min entropia)
    pxy = ct / n
    px = pxy.sum(1, keepdims=True)
    py = pxy.sum(0, keepdims=True)
    nz = pxy > 0
    mi = (pxy[nz] * np.log(pxy[nz] / (px @ py)[nz])).sum()
    hx = -(px[px > 0] * np.log(px[px > 0])).sum()
    hy = -(py[py > 0] * np.log(py[py > 0])).sum()
    return v, mi / max(1e-12, min(hx, hy))


def sweep(src, cols, label, pairs=None):
    res = []
    pairs = pairs or list(itertools.combinations(cols, 2))
    for a, b in pairs:
        df = con.execute(f"SELECT {a}::VARCHAR a, {b}::VARCHAR b, count(*) n FROM {src} GROUP BY 1,2").df()
        ct = df.pivot_table(index='a', columns='b', values='n', aggfunc='sum', fill_value=0).values.astype(float)
        v, nmi = cramers_v_corr(ct)
        res.append((label, a, b, ct.shape[0], ct.shape[1], v, nmi))
    r = pd.DataFrame(res, columns=['lvl', 'a', 'b', 'ka', 'kb', 'V', 'NMI']).sort_values('V', ascending=False)
    return r


src = f"'{OUT}/tx_cat_sample.parquet'"
txcols = con.execute(f"DESCRIBE SELECT * FROM {src}").df()['column_name'].tolist()
r_tx = sweep(src, txcols, 'tx')
print('tx sweep', time.time() - t0, flush=True)

cucols_sql = """(SELECT document_type, gender, country, coalesce(detected_accent,'∅') accent, segment, coalesce(occupation,'∅') occupation,
 coalesce(marital_status,'∅') marital, coalesce(education_level,'∅') education, cstatus, CAST(mkt AS VARCHAR) mkt,
 split_part(email,'@',2) email_dom, state, city, CASE WHEN landline_phone IS NULL THEN 'no' ELSE 'yes' END landline,
 CAST(floor(date_diff('day', dob, DATE '2026-06-17')/3652.5) AS VARCHAR) age_dec,
 CAST(ntile(10) OVER (PARTITION BY country ORDER BY income) AS VARCHAR) inc_dec,
 CASE WHEN income IS NULL THEN 'null' ELSE 'v' END inc_null, CASE WHEN credit_score IS NULL THEN 'null' ELSE 'v' END cs_null,
 CAST(ntile(10) OVER (ORDER BY credit_score) AS VARCHAR) cs_dec, CAST(year(registration_date) AS VARCHAR) reg_yr,
 CAST(year(last_updated) AS VARCHAR) upd_yr, CASE WHEN registration_branch_id IS NULL THEN 'null' ELSE 'v' END regbr_null,
 left(postal_code,1) pc1, CAST(length(document_number) AS VARCHAR) doc_len
 FROM cu)"""
cucols = con.execute(f"DESCRIBE SELECT * FROM {cucols_sql}").df()['column_name'].tolist()
r_cu = sweep(cucols_sql, cucols, 'cu')
print('cu sweep', time.time() - t0, flush=True)

prcols_sql = """(SELECT ptype, currency, pstatus, opening_channel, CAST(app AS VARCHAR) app,
 CASE WHEN dpd IS NULL THEN 'null' WHEN dpd=0 THEN '0' WHEN dpd<30 THEN '1-29' WHEN dpd<90 THEN '30-89' ELSE '90+' END dpd_b,
 CAST(ntile(10) OVER (PARTITION BY ptype ORDER BY rate) AS VARCHAR) rate_dec,
 CAST(ntile(10) OVER (PARTITION BY ptype, currency ORDER BY bal) AS VARCHAR) bal_dec,
 CASE WHEN credit_limit IS NULL THEN 'null' ELSE CAST(ntile(5) OVER (PARTITION BY ptype, currency ORDER BY credit_limit) AS VARCHAR) END lim_q,
 CAST(year(opened) AS VARCHAR) open_yr, CASE WHEN expires IS NULL THEN 'null' WHEN expires < DATE '2026-06-17' THEN 'expired' ELSE 'future' END exp_b,
 CASE WHEN last_tx IS NULL THEN 'null' ELSE 'v' END lasttx_null, left(product_number,2) pnum_pfx, CAST(length(product_number) AS VARCHAR) pnum_len,
 CASE WHEN opening_branch_id IS NULL THEN 'null' ELSE 'v' END obr_null, CAST(year(last_updated) AS VARCHAR) upd_yr
 FROM pr)"""
prcols = con.execute(f"DESCRIBE SELECT * FROM {prcols_sql}").df()['column_name'].tolist()
r_pr = sweep(prcols_sql, prcols, 'pr')
print('pr sweep', time.time() - t0, flush=True)

allr = pd.concat([r_tx, r_cu, r_pr])
allr.to_csv(f'{OUT}/hunt_07_cramer.csv', index=False)
pd.set_option('display.width', 200)
for lvl, r in [('tx', r_tx), ('cu', r_cu), ('pr', r_pr)]:
    print(f'==== {lvl}: top 45 por V ({len(r)} pares)')
    print(r.head(45).to_string(index=False, float_format=lambda x: f'{x:.4f}'))
