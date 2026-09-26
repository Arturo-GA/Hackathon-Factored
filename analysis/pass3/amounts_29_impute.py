import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
q("""with m as (select merchant_name, any_value(mcat) mc from tx where mcat is not null and merchant_name is not null group by 1)
select count(*) n_purch,
 avg((t.mcat is null)::int) mcat_null,
 avg((coalesce(t.mcat, m.mc, t.tcat) is null)::int) cat_null_after_impute,
 avg((t.tcat is null)::int) tcat_null,
 avg((t.mcat is not null and t.tcat is not null and t.mcat<>t.tcat)::int) mismatch,
 avg((t.merchant_name is not null and t.mcat is not null and m.mc<>t.mcat)::int) merch_mismatch
from tx t left join m using(merchant_name) where t.ttype='Purchase'""")
# per-customer clustering of amount_usd nulls in ARS/COP
q("""with c as (select customer_id, count(*) n, avg((amount_usd is null)::int) r from tx where currency<>'USD' group by 1 having count(*)>=20)
 select count(*) nc, var_samp(r) var_obs, avg(0.05*0.95/n) var_exp from c""")
# merchant share within category
q("select mcat, count(distinct merchant_name) nm, count(*) n, count(*)/sum(count(*)) over () shr from tx where mcat is not null and merchant_name is not null group by 1 order by 3 desc")
