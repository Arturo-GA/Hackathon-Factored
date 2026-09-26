import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
print("== 1. merchant -> mcat (incl. casing/whitespace variants)")
q("""select count(distinct merchant_name) nm, count(distinct lower(trim(merchant_name))) nm_norm,
 count(distinct (merchant_name, mcat)) pairs from tx where merchant_name is not null and mcat is not null""")
q("""select mcat, merchant_name, count(*) n from tx where merchant_name is not null group by all order by 1,2""")
print("== 2. tcat vs mcat, all ttypes")
q("""select ttype, count(*) n, sum((tcat is not null)::int) tcat_nn, sum((mcat is not null)::int) mcat_nn, sum((merchant_name is not null)::int) merch_nn,
  sum((mcat is not null and tcat is not null)::int) both_nn, sum((mcat is not null and tcat is not null and mcat<>tcat)::int) mism
  from tx group by 1 order by 2 desc""")
q("""select ttype, tcat, count(*) n from tx where ttype in ('Payment','Purchase') group by all order by 1,3 desc""")
print("== 3. null independence in Purchase")
q("""select count(*) n, avg((mcat is null)::int) p_m, avg((tcat is null)::int) p_t, avg((merchant_name is null)::int) p_n,
  avg((mcat is null and tcat is null)::int) p_mt, avg((mcat is null)::int)*avg((tcat is null)::int) exp_mt,
  avg((mcat is null and merchant_name is null)::int) p_mn, avg((mcat is null)::int)*avg((merchant_name is null)::int) exp_mn,
  avg((tcat is null and merchant_name is null)::int) p_tn,
  avg((mcat is null and tcat is null and merchant_name is null)::int) p_all
  from tx where ttype='Purchase'""")
print("== 4. imputation step by step (Purchase)")
q("""with m as (select merchant_name, any_value(mcat) mc from tx where mcat is not null and merchant_name is not null group by 1)
select count(*) n,
 avg((t.mcat is null)::int) null_mcat,
 avg((coalesce(t.mcat,t.tcat) is null)::int) null_after_tcat,
 avg((coalesce(t.mcat,m.mc) is null)::int) null_after_merch,
 avg((coalesce(t.mcat,m.mc,t.tcat) is null)::int) null_all,
 avg((t.merchant_name is null)::int) null_merch_name
from tx t left join m using(merchant_name) where t.ttype='Purchase'""")
print("== 5. channel x ttype (Cramer V) and channel shares per ttype")
df = con.execute("select ttype, channel, count(*) n from tx group by all").df()
ct = df.pivot(index='ttype', columns='channel', values='n').fillna(0)
from scipy.stats import chi2_contingency
chi2 = chi2_contingency(ct.values)[0]; N = ct.values.sum()
V = np.sqrt(chi2/(N*(min(ct.shape)-1)))
print(ct.astype(int).to_string()); print((ct.div(ct.sum(1),axis=0)).round(4).to_string()); print('Cramer V ttype x channel =', round(V,4), 'N=',int(N), '\n')
print("== 6. category vs other vars (channel/country/status/amount) in Purchase")
df = con.execute("select coalesce(mcat,tcat) c, channel, count(*) n from tx where ttype='Purchase' and coalesce(mcat,tcat) is not null group by all").df()
ct = df.pivot(index='c', columns='channel', values='n').fillna(0); chi2=chi2_contingency(ct.values)[0]; N=ct.values.sum()
print('V cat x channel', round(np.sqrt(chi2/(N*(min(ct.shape)-1))),4))
df = con.execute("select coalesce(mcat,tcat) c, country, count(*) n from tx where ttype='Purchase' and coalesce(mcat,tcat) is not null and country is not null group by all").df()
ct = df.pivot(index='c', columns='country', values='n').fillna(0); chi2=chi2_contingency(ct.values)[0]; N=ct.values.sum()
print('V cat x country', round(np.sqrt(chi2/(N*(min(ct.shape)-1))),4))
q("""select coalesce(mcat,tcat) c, count(*) n, median(amount_usd) med_usd, avg(fraud::int)*100 fraud_pct, avg((status='Declined')::int) decl from tx where ttype='Purchase' group by 1 order by 2 desc""")
print("== 7. merchant vs country / city (is merchant local?)")
q("""select merchant_name, count(distinct country) nctry, count(distinct city) ncity from tx where merchant_name is not null group by 1 order by 1 limit 30""")
