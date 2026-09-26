"""hunt_03: construye tabla ancha por cliente (features de TODAS las tablas) en analysis/pass3/hunt_cache/*.parquet.
Cada fuente se agrega en SQL (DuckDB) y se escribe en un parquet separado; luego se unen en pandas (150k filas).
Montos convertidos a USD con tasas ~constantes (USD 1, COP 4000, ARS 350; income MXN 17).
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_03_build_customer.py
"""
import duckdb, time, os
import pandas as pd

OUT = 'analysis/pass3/hunt_cache'
os.makedirs(OUT, exist_ok=True)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

USD = "(amount / CASE currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END)"
REF = "TIMESTAMP '2026-06-17 23:59:59'"

def cnt(col, vals, prefix):
    return ",\n".join([f"count(*) FILTER (WHERE {col}='{v}') AS {prefix}_{v.lower().replace(' ','_')}" for v in vals])

def run(name, sql):
    t = time.time()
    con.execute(f"COPY ({sql}) TO '{OUT}/cust_{name}.parquet' (FORMAT parquet)")
    n = con.execute(f"SELECT count(*) FROM '{OUT}/cust_{name}.parquet'").fetchone()[0]
    print(name, n, f"{time.time()-t:.1f}s", flush=True)

# ---------- TX ----------
ttypes = ['Purchase','Withdrawal','Transfer','Payment','Deposit','Adjustment']
chans = ['POS','ATM','Web','App','Branch','Transfer']
tcats = ['Food','Services','Other','Transport','Entertainment','Health']
sql_tx = f"""
SELECT t.customer_id,
 count(*) AS tx_n,
 count(DISTINCT t.product_id) AS tx_nprod,
 sum({USD}) AS tx_sum_usd, avg({USD}) AS tx_avg_usd, max({USD}) AS tx_max_usd,
 avg(ln(1+{USD})) AS tx_avg_lusd, stddev_samp(ln(1+{USD})) AS tx_sd_lusd,
 {cnt('ttype', ttypes, 'tx_t')},
 {",".join([f"sum({USD}) FILTER (WHERE ttype='{v}') AS tx_usd_{v.lower()}" for v in ttypes])},
 {cnt('channel', chans, 'tx_ch')},
 {cnt('tcat', tcats, 'tx_cat')},
 count(*) FILTER (WHERE status='Declined') AS tx_declined,
 count(*) FILTER (WHERE status='Pending') AS tx_pending,
 count(*) FILTER (WHERE status='Reversed') AS tx_reversed,
 count(*) FILTER (WHERE code='05') AS tx_c05, count(*) FILTER (WHERE code='14') AS tx_c14,
 count(*) FILTER (WHERE code='51') AS tx_c51, count(*) FILTER (WHERE code='54') AS tx_c54,
 count(*) FILTER (WHERE code IS NULL) AS tx_cnull,
 count(*) FILTER (WHERE fraud) AS tx_fraud,
 avg(fscore) AS tx_fscore_avg, max(fscore) AS tx_fscore_max,
 count(*) FILTER (WHERE fscore IS NULL) AS tx_fscore_null,
 count(*) FILTER (WHERE fscore>=50) AS tx_fscore_ge50,
 count(*) FILTER (WHERE t.country <> c.country) AS tx_foreign,
 count(*) FILTER (WHERE t.country IN ('USA','Spain','Brazil')) AS tx_intl,
 count(DISTINCT t.country) AS tx_ncountry,
 count(DISTINCT t.city) AS tx_ncity,
 count(DISTINCT merchant_name) AS tx_nmerchant,
 count(merchant_name) AS tx_with_merchant,
 count(branch_id) AS tx_with_branch,
 count(DISTINCT branch_id) AS tx_nbranch,
 count(DISTINCT t.currency) AS tx_ncur,
 epoch(min(t.ts))/86400.0 AS tx_first_day, epoch(max(t.ts))/86400.0 AS tx_last_day,
 date_diff('day', max(t.ts), {REF}) AS tx_days_since_last,
 date_diff('day', min(t.ts), max(t.ts)) AS tx_span_days,
 count(DISTINCT CAST(t.ts AS DATE)) AS tx_active_days,
 avg(CASE WHEN dayofweek(t.ts) IN (0,6) THEN 1 ELSE 0 END) AS tx_weekend_share,
 avg(CASE WHEN hour(t.ts) < 6 THEN 1 ELSE 0 END) AS tx_night_share,
 avg(hour(t.ts)) AS tx_hour_avg, stddev_samp(hour(t.ts)) AS tx_hour_sd,
 avg(day(t.ts)) AS tx_dom_avg,
 avg(CASE WHEN day(t.ts) IN (1,2,15,16,30,31) THEN 1 ELSE 0 END) AS tx_payday_share,
 avg(date_diff('day', CAST(t.ts AS DATE), t.process_date)) AS tx_proc_lag,
 count(*) FILTER (WHERE t.ts >= TIMESTAMP '2025-12-17') AS tx_n_last6m,
 stddev_samp(t.lat) AS tx_lat_sd, stddev_samp(t.lon) AS tx_lon_sd,
 count(*) FILTER (WHERE t.lat IS NULL) AS tx_latnull,
 count(*) FILTER (WHERE t.country_raw <> t.country) AS tx_country_raw_diff,
 avg(CASE WHEN {USD} = round({USD}) THEN 1 ELSE 0 END) AS tx_round_share
FROM tx t LEFT JOIN cu c USING (customer_id)
GROUP BY t.customer_id
"""
run('tx', sql_tx)

# ---------- CC ----------
cats = ['Transaccional','Producto','Queja','Técnico','Comercial','Retención']
itypes = ['Inbound Call','Outbound Call','Chat','Email','Video']
sql_cc = f"""
SELECT customer_id, count(*) AS cc_n,
 {",".join([f"count(*) FILTER (WHERE cat='{v}') AS cc_cat_{i}" for i,v in enumerate(cats)])},
 {",".join([f"count(*) FILTER (WHERE itype='{v}') AS cc_it_{i}" for i,v in enumerate(itypes)])},
 avg(dur) AS cc_dur, avg(wait) AS cc_wait,
 avg(CASE WHEN resolved THEN 1 ELSE 0 END) AS cc_fcr,
 avg(CASE WHEN followup THEN 1 ELSE 0 END) AS cc_followup,
 avg(CASE WHEN escalated THEN 1 ELSE 0 END) AS cc_escal,
 avg(sent_score) AS cc_sent, count(*) FILTER (WHERE sent IN ('Negativo','Muy Negativo')) AS cc_neg,
 count(*) FILTER (WHERE has_transcript) AS cc_transcript,
 count(mentioned_products) AS cc_with_mention,
 count(DISTINCT agent_id) AS cc_nagents,
 count(*) FILTER (WHERE c_acc IS NULL) AS cc_cacc_null,
 date_diff('day', max(ts), {REF}) AS cc_days_since_last
FROM cc GROUP BY customer_id
"""
run('cc', sql_cc)

# ---------- CP ----------
pcats = ['Transactions','Fees','Technical','Branch','Service']
ctypes = ['Complaint','Claim','Request','Suggestion']
sql_cp = f"""
SELECT customer_id, count(*) AS cp_n,
 {",".join([f"count(*) FILTER (WHERE category='{v}') AS cp_cat_{v.lower()}" for v in pcats])},
 {",".join([f"count(*) FILTER (WHERE case_type='{v}') AS cp_ct_{v.lower()}" for v in ctypes])},
 count(*) FILTER (WHERE priority IN ('High','Critical')) AS cp_high,
 count(*) FILTER (WHERE rchan='Regulator') AS cp_regulator,
 sum(claimed / CASE currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 WHEN 'MXN' THEN 17.0 ELSE 1.0 END) AS cp_claimed_usd,
 sum(compensation) AS cp_comp,
 max(CASE WHEN repeat THEN 1 ELSE 0 END) AS cp_repeat_any,
 count(*) FILTER (WHERE repeat) AS cp_repeat_n,
 avg(res_sat) AS cp_res_sat, avg(CASE WHEN sla THEN 1 ELSE 0 END) AS cp_sla, avg(rdays) AS cp_rdays,
 count(*) FILTER (WHERE status IN ('Open','In Process')) AS cp_open
FROM cp GROUP BY customer_id
"""
run('cp', sql_cp)

# ---------- SV ----------
sql_sv = f"""
SELECT customer_id, count(*) AS sv_n,
 avg(score) FILTER (WHERE survey_type='CSAT') AS sv_csat,
 avg(score) FILTER (WHERE survey_type='NPS') AS sv_nps,
 avg(score) FILTER (WHERE survey_type='CES') AS sv_ces,
 count(*) FILTER (WHERE nps_category='Detractor') AS sv_detractor,
 count(*) FILTER (WHERE comment_sentiment='Negative') AS sv_comment_neg,
 avg(resp_hours) AS sv_resp_hours, avg(campaign_response_rate) AS sv_crr
FROM sv GROUP BY customer_id
"""
run('sv', sql_sv)

# ---------- CS ----------
schans = ['Email','SMS','WhatsApp','Push','Voice']
sql_cs = f"""
SELECT customer_id, count(*) AS cs_n,
 {",".join([f"count(*) FILTER (WHERE send_channel='{v}') AS cs_ch_{v.lower()}" for v in schans])},
 avg(CASE WHEN delivered THEN 1 ELSE 0 END) AS cs_deliv, avg(CASE WHEN opened THEN 1 ELSE 0 END) AS cs_open,
 avg(CASE WHEN clicked THEN 1 ELSE 0 END) AS cs_click, count(*) FILTER (WHERE conv) AS cs_conv,
 sum(conv_value) AS cs_conv_value, count(*) FILTER (WHERE send_status<>'Sent') AS cs_fail,
 count(*) FILTER (WHERE failure_reason='User blocked sender') AS cs_blocked,
 count(*) FILTER (WHERE failure_reason='Invalid email address') AS cs_invalid_email,
 count(DISTINCT campaign_id) AS cs_ncamp, sum(send_cost) AS cs_cost
FROM cs GROUP BY customer_id
"""
run('cs', sql_cs)

# ---------- DE ----------
etypes = ['PageView','Click','Login','Logout','FormSubmit','Error','Purchase']
dchans = ['Android App','iOS App','Desktop Web','Mobile Web']
sql_de = f"""
SELECT d.customer_id, count(*) AS de_n, count(DISTINCT session_id) AS de_nsess,
 {",".join([f"count(*) FILTER (WHERE event_type='{v}') AS de_et_{v.lower()}" for v in etypes])},
 {",".join([f"count(*) FILTER (WHERE d.channel='{v}') AS de_ch_{i}" for i,v in enumerate(dchans)])},
 count(*) FILTER (WHERE action='initiate_payment') AS de_a_pay,
 count(*) FILTER (WHERE action='initiate_transfer') AS de_a_transfer,
 count(*) FILTER (WHERE action='view_help') AS de_a_help,
 count(*) FILTER (WHERE action='view_transactions') AS de_a_viewtx,
 avg(d.dur) AS de_dur, sum(event_value) AS de_value_sum, count(event_value) AS de_value_n,
 count(d.product_id) AS de_with_prod,
 count(DISTINCT ip_address) AS de_nip,
 count(*) FILTER (WHERE replace(ip_country,'Mexico','México') <> c.country) AS de_ip_foreign,
 count(referrer) AS de_referrer_n, count(utm_source) AS de_utm_n,
 count(DISTINCT app_version) AS de_napp_ver,
 date_diff('day', max(d.ts), {REF}) AS de_days_since_last
FROM de d LEFT JOIN cu c USING (customer_id)
WHERE d.customer_id IS NOT NULL
GROUP BY d.customer_id
"""
run('de', sql_de)

# ---------- PR ----------
ptypes = ['Cuenta Ahorro','Tarjeta Crédito','Cuenta Corriente','Tarjeta Débito','Préstamo Personal','Préstamo Hipotecario','Inversión','Seguro']
pst = ['Active','Closed','Blocked','Suspended']
sql_pr = f"""
SELECT customer_id, count(*) AS pr_n,
 {",".join([f"count(*) FILTER (WHERE ptype='{v}') AS pr_pt_{i}" for i,v in enumerate(ptypes)])},
 {",".join([f"count(*) FILTER (WHERE pstatus='{v}') AS pr_st_{v.lower()}" for v in pst])},
 sum(bal / CASE currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END) AS pr_bal_usd,
 sum(credit_limit / CASE currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END) AS pr_limit_usd,
 avg(rate) AS pr_rate, avg(CASE WHEN app THEN 1 ELSE 0 END) AS pr_app_share,
 max(dpd) AS pr_dpd_max, count(*) FILTER (WHERE dpd>0) AS pr_dpd_pos,
 date_diff('day', min(opened), DATE '2026-06-17') AS pr_tenure,
 date_diff('day', max(opened), DATE '2026-06-17') AS pr_newest,
 count(*) FILTER (WHERE opening_channel='Branch') AS pr_oc_branch,
 count(*) FILTER (WHERE opening_channel IN ('Web','App')) AS pr_oc_digital,
 count(DISTINCT currency) AS pr_ncur,
 count(last_tx) AS pr_with_lasttx
FROM pr GROUP BY customer_id
"""
run('pr', sql_pr)

# ---------- CU ----------
sql_cu = """
SELECT customer_id, document_type, gender, country, detected_accent, segment, credit_score,
 income / CASE country WHEN 'Colombia' THEN 4000.0 WHEN 'Argentina' THEN 350.0 ELSE 17.0 END AS income_usd,
 occupation, marital_status, education_level, cstatus, CAST(mkt AS INT) AS mkt,
 date_diff('day', dob, DATE '2026-06-17')/365.25 AS age,
 date_diff('day', registration_date, TIMESTAMP '2026-06-17') AS reg_days,
 date_diff('day', last_updated, TIMESTAMP '2026-06-17') AS lastupd_days,
 CASE WHEN landline_phone IS NULL THEN 1 ELSE 0 END AS no_landline,
 CASE WHEN email IS NULL THEN 1 ELSE 0 END AS no_email,
 split_part(email,'@',2) AS email_domain,
 state, city,
 length(address) AS addr_len
FROM cu
"""
run('cu', sql_cu)

# merge
base = pd.read_parquet(f'{OUT}/cust_cu.parquet')
for n in ['tx','cc','cp','sv','cs','de','pr']:
    d = pd.read_parquet(f'{OUT}/cust_{n}.parquet')
    base = base.merge(d, on='customer_id', how='left')
num = base.select_dtypes('number').columns
base[num] = base[num].astype('float32')
base.to_parquet(f'{OUT}/cust_wide.parquet')
print(base.shape)
print(base.isna().mean().sort_values(ascending=False).head(20))
