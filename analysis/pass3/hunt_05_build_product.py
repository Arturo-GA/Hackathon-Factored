"""hunt_05: tabla ancha por producto (pr + agregados de tx, de, cc.mentioned_products, cp.affected_product_id, atributos del cliente).
Salida: analysis/pass3/hunt_cache/prod_wide.parquet
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_05_build_product.py
"""
import duckdb, time
import pandas as pd

OUT = 'analysis/pass3/hunt_cache'
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
USD = "(amount / CASE currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END)"
REF = "TIMESTAMP '2026-06-17 23:59:59'"


def run(name, sql):
    t = time.time()
    con.execute(f"COPY ({sql}) TO '{OUT}/prod_{name}.parquet' (FORMAT parquet)")
    print(name, con.execute(f"SELECT count(*) FROM '{OUT}/prod_{name}.parquet'").fetchone()[0], f"{time.time()-t:.1f}s", flush=True)


ttypes = ['Purchase', 'Withdrawal', 'Transfer', 'Payment', 'Deposit', 'Adjustment']
chans = ['POS', 'ATM', 'Web', 'App', 'Branch', 'Transfer']
run('tx', f"""
SELECT product_id, count(*) AS ptx_n, sum({USD}) AS ptx_sum_usd, avg(ln(1+{USD})) AS ptx_avg_lusd, max({USD}) AS ptx_max_usd,
 {",".join([f"count(*) FILTER (WHERE ttype='{v}') AS ptx_t_{v.lower()}" for v in ttypes])},
 {",".join([f"sum({USD}) FILTER (WHERE ttype='{v}') AS ptx_usd_{v.lower()}" for v in ttypes])},
 {",".join([f"count(*) FILTER (WHERE channel='{v}') AS ptx_ch_{v.lower()}" for v in chans])},
 count(*) FILTER (WHERE status='Declined') AS ptx_declined, count(*) FILTER (WHERE status='Pending') AS ptx_pending,
 count(*) FILTER (WHERE status='Reversed') AS ptx_reversed,
 count(*) FILTER (WHERE code='05') AS ptx_c05, count(*) FILTER (WHERE code='14') AS ptx_c14,
 count(*) FILTER (WHERE code='51') AS ptx_c51, count(*) FILTER (WHERE code='54') AS ptx_c54,
 count(*) FILTER (WHERE fraud) AS ptx_fraud, avg(fscore) AS ptx_fscore,
 count(*) FILTER (WHERE country IN ('USA','Spain','Brazil')) AS ptx_intl,
 count(DISTINCT merchant_name) AS ptx_nmerch,
 date_diff('day', max(ts), {REF}) AS ptx_days_since_last, date_diff('day', min(ts), {REF}) AS ptx_days_since_first,
 date_diff('day', min(ts), max(ts)) AS ptx_span,
 count(*) FILTER (WHERE ts >= TIMESTAMP '2025-12-17') AS ptx_n_last6m,
 max(ts) AS ptx_max_ts, min(ts) AS ptx_min_ts
FROM tx GROUP BY product_id""")

run('de', f"""
SELECT product_id, count(*) AS pde_n, count(DISTINCT customer_id) AS pde_ncust,
 count(*) FILTER (WHERE event_type='Error') AS pde_err, count(*) FILTER (WHERE event_type='Purchase') AS pde_purch,
 sum(event_value) AS pde_value, date_diff('day', max(ts), {REF}) AS pde_days_since_last
FROM de WHERE product_id IS NOT NULL GROUP BY product_id""")

run('cc', f"""
SELECT trim(pid) AS product_id, count(*) AS pcc_n,
 count(*) FILTER (WHERE cat='Transaccional') AS pcc_trans, count(*) FILTER (WHERE cat='Queja') AS pcc_queja,
 count(*) FILTER (WHERE cat='Retención') AS pcc_ret, avg(CASE WHEN resolved THEN 1 ELSE 0 END) AS pcc_fcr,
 count(DISTINCT customer_id) AS pcc_ncust
FROM (SELECT *, unnest(string_split(mentioned_products, ',')) AS pid FROM cc WHERE mentioned_products IS NOT NULL)
GROUP BY 1""")

run('cp', """
SELECT affected_product_id AS product_id, count(*) AS pcp_n, count(*) FILTER (WHERE category='Transactions') AS pcp_trans,
 count(*) FILTER (WHERE priority IN ('High','Critical')) AS pcp_high
FROM cp WHERE affected_product_id IS NOT NULL GROUP BY 1""")

run('pr', f"""
SELECT p.product_id, p.customer_id, p.ptype, p.currency AS pcur, p.pstatus, p.opening_channel, CAST(p.app AS INT) AS app, p.dpd,
 p.bal / CASE p.currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END AS bal_usd,
 p.credit_limit / CASE p.currency WHEN 'COP' THEN 4000.0 WHEN 'ARS' THEN 350.0 ELSE 1.0 END AS limit_usd,
 p.bal / nullif(p.credit_limit,0) AS util,
 p.rate, date_diff('day', p.opened, DATE '2026-06-17') AS age_days, date_diff('day', DATE '2026-06-17', p.expires) AS days_to_exp,
 date_diff('day', p.opened, p.expires) AS term_days,
 date_diff('day', p.last_tx, {REF}) AS lasttx_days, date_diff('day', p.last_updated, {REF}) AS lastupd_days,
 CASE WHEN p.last_tx IS NULL THEN 1 ELSE 0 END AS lasttx_null,
 length(p.product_number) AS pnum_len, left(p.product_number, 2) AS pnum_pfx,
 CASE WHEN b.branch_id IS NULL AND p.opening_branch_id IS NOT NULL THEN 1 ELSE 0 END AS open_branch_missing,
 CASE WHEN p.opening_branch_id IS NULL THEN 1 ELSE 0 END AS open_branch_null,
 CASE WHEN b.country IS NOT NULL AND b.country <> c.country THEN 1 ELSE 0 END AS open_branch_foreign,
 c.segment, c.credit_score, c.income / CASE c.country WHEN 'Colombia' THEN 4000.0 WHEN 'Argentina' THEN 350.0 ELSE 17.0 END AS income_usd,
 c.cstatus, c.country AS ccountry, CAST(c.mkt AS INT) AS mkt, date_diff('day', c.dob, DATE '2026-06-17')/365.25 AS cage,
 date_diff('day', c.registration_date, p.opened) AS open_minus_reg,
 c.gender, c.occupation, c.education_level, c.marital_status,
 count(*) OVER (PARTITION BY p.customer_id) AS c_nprod,
 row_number() OVER (PARTITION BY p.customer_id ORDER BY p.opened) AS prod_rank
FROM pr p LEFT JOIN cu c USING (customer_id) LEFT JOIN br b ON b.branch_id = p.opening_branch_id""")

base = pd.read_parquet(f'{OUT}/prod_pr.parquet')
for n in ['tx', 'de', 'cc', 'cp']:
    base = base.merge(pd.read_parquet(f'{OUT}/prod_{n}.parquet'), on='product_id', how='left')
# features de cliente: agregados de contacto/reclamos de la tabla cliente
cw = pd.read_parquet(f'{CACHE}/cust_wide.parquet' if False else f'{OUT}/cust_wide.parquet',
                     columns=['customer_id', 'cc_n', 'cc_fcr', 'cp_n', 'sv_csat', 'de_n', 'cs_n', 'tx_n', 'tx_declined', 'tx_fraud'])
cw.columns = ['customer_id'] + ['cust_' + c for c in cw.columns[1:]]
base = base.merge(cw, on='customer_id', how='left')
base['lasttx_minus_ptx'] = (base['lasttx_days'] - base['ptx_days_since_last'])
base = base.drop(columns=['ptx_max_ts', 'ptx_min_ts'])
num = base.select_dtypes('number').columns
base[num] = base[num].astype('float32')
base.to_parquet(f'{OUT}/prod_wide.parquet')
print(base.shape)
print(base[['lasttx_null', 'ptx_n', 'pde_n', 'pcc_n', 'pcp_n']].notna().mean())
print(base['pnum_pfx'].value_counts().head(10))
