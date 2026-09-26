import duckdb, numpy as np, pandas as pd
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
def q(title, s):
    print('==', title); print(con.execute(s).df().to_string(), '\n')

# 1. merchant -> mcat cardinality
q('merchant -> n mcat', """select merchant_name, count(distinct mcat) n_mcat, any_value(mcat) mcat, count(*) n,
   sum((mcat is null)::int) n_mcat_null
   from tx where merchant_name is not null group by 1 order by mcat, n desc""")
q('summary merchants', """select count(distinct merchant_name) n_merch,
   (select count(*) from (select merchant_name from tx where merchant_name is not null and mcat is not null group by 1 having count(distinct mcat)>1)) n_conflict
   from tx""")
# 2. presence by ttype
q('presence by ttype', """select ttype, count(*) n,
   avg((merchant_name is not null)::int) p_merch, avg((mcat is not null)::int) p_mcat, avg((tcat is not null)::int) p_tcat
   from tx group by 1 order by 2 desc""")
# 3. tcat vs mcat mismatch overall
q('mcat vs tcat', """select ttype, count(*) n_both, sum((mcat<>tcat)::int) n_mismatch
   from tx where mcat is not null and tcat is not null group by 1""")
q('tcat values by ttype', """select ttype, tcat, count(*) n from tx where ttype in ('Purchase','Payment') group by 1,2 order by 1,3 desc""")
# 4. null independence in Purchase
q('null patterns in Purchase', """select (merchant_name is null) m_null, (mcat is null) mc_null, (tcat is null) t_null, count(*) n,
   count(*)/sum(count(*)) over () p from tx where ttype='Purchase' group by 1,2,3 order by 4 desc""")
q('marginals Purchase', """select count(*) n, avg((merchant_name is null)::int) pm, avg((mcat is null)::int) pmc, avg((tcat is null)::int) pt,
   avg((merchant_name is null and mcat is null)::int) p_m_mc, avg((mcat is null and tcat is null)::int) p_mc_t,
   avg((merchant_name is null and mcat is null and tcat is null)::int) p_all
   from tx where ttype='Purchase'""")
# 5. imputation
q('imputation', """with m as (select merchant_name, any_value(mcat) mc from tx where mcat is not null and merchant_name is not null group by 1)
   select t.ttype, count(*) n, avg((t.mcat is null)::int) mcat_null,
   avg((coalesce(t.mcat, m.mc) is null)::int) after_map,
   avg((coalesce(t.mcat, m.mc, t.tcat) is null)::int) after_map_tcat,
   sum((coalesce(t.mcat, m.mc, t.tcat) is null)::int) n_still_null,
   avg((coalesce(t.merchant_name) is null)::int) merch_null
   from tx t left join m using(merchant_name) where t.ttype in ('Purchase','Payment') group by 1""")
# 6. weights
q('mcat weights', """select mcat, count(distinct merchant_name) nm, count(*) n, count(*)/sum(count(*)) over () shr
   from tx where mcat is not null group by 1 order by 3 desc""")
q('merchant share within mcat', """with a as (select mcat, merchant_name, count(*) n from tx where mcat is not null and merchant_name is not null group by 1,2)
   select mcat, min(n) mn, max(n) mx, max(n)/min(n)::double ratio from a group by 1""")
# chi2 uniformity within category
df = con.execute("select mcat, merchant_name, count(*) n from tx where mcat is not null and merchant_name is not null group by 1,2").df()
from scipy.stats import chisquare
for c, g in df.groupby('mcat'):
    s = chisquare(g.n.values); print(c, len(g), 'chi2 p=%.3g' % s.pvalue, 'max dev %.3f%%' % (100*np.max(np.abs(g.n/g.n.mean()-1))))
# 7. channel x ttype
ct = con.execute("select ttype, channel, count(*) n from tx group by 1,2").df().pivot(index='ttype', columns='channel', values='n').fillna(0)
print(ct.astype(int).to_string())
print((ct.div(ct.sum(1), axis=0)).round(4).to_string())
from scipy.stats import chi2_contingency
chi2, p, dof, _ = chi2_contingency(ct.values)
N = ct.values.sum(); V = np.sqrt(chi2/(N*(min(ct.shape)-1)))
print('Cramer V ttype x channel = %.4f' % V)
q('channel null', "select avg((channel is null)::int) p_null, avg((ttype is null)::int) t_null from tx")
# 8. Payment tcat: is it related to product type / channel? (semantics check)
ct2 = con.execute("""select p.ptype, t.tcat, count(*) n from tx t join pr p using(product_id)
   where t.ttype='Payment' and t.tcat is not null group by 1,2""").df().pivot(index='ptype', columns='tcat', values='n').fillna(0)
print(ct2.div(ct2.sum(axis=1), axis=0).round(3).to_string())
chi2, p, dof, _ = chi2_contingency(ct2.values); N = ct2.values.sum()
print('Cramer V ptype x tcat (Payment) = %.4f' % np.sqrt(chi2/(N*(min(ct2.shape)-1))))
