import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
# complaints claimed vs tx amounts same customer
q("""with c as (select complaint_id, customer_id, claimed, currency, ts from cp where claimed is not null)
select count(distinct c.complaint_id) n_match_amount, (select count(*) from c) n_cp from c join tx t on t.customer_id=c.customer_id and abs(t.amount-c.claimed)<0.005""")
q("""with c as (select complaint_id, customer_id, claimed, currency, ts from cp where claimed is not null)
select count(distinct c.complaint_id) n_match_usd from c join tx t on t.customer_id=c.customer_id and abs(coalesce(t.amount_usd, case when t.currency='USD' then t.amount end)-c.claimed)<0.005""")
# any-customer exact matches (baseline chance)
q("""with c as (select complaint_id, claimed from cp where claimed is not null)
select count(distinct c.complaint_id) n_match_any from c join (select distinct amount from tx where currency='USD') t on abs(t.amount - c.claimed)<0.005""")
# cp claimed vs case type / category
q("select case_type, category, count(*) n, avg((claimed is not null)::int) has_claim, median(claimed) med, max(claimed) mx from cp group by all order by n desc limit 30")
q("select category, subcategory, count(*) n, avg((claimed is not null)::int) has_claim from cp group by all order by 1, n desc")
