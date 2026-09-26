import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('##',t), print(con.execute(s).df().to_string(), '\n'))
con.execute("""create temp table b as select t.transaction_id, t.customer_id, t.channel, t.ts, t.country tc, t.city tcity, t.branch_id, t.status, t.fraud,
  cu.country cc, cu.city ccity, br.branch_id br_found, br.country bc, br.city bcity, br.opened bopened, br.branch_status bstatus, br.branch_type btype
  from tx t join cu using(customer_id) left join br on br.branch_id=t.branch_id where t.branch_id is not null""")
q("branch found in br", "select count(*) n, sum((br_found is null)::int) missing from b")
q("branch country vs customer/tx country", """select (tc<>cc) foreign_, count(*) n, round(avg((bc=cc)::int),5) br_home, round(avg((bc=tc)::int),5) br_txcountry,
  round(avg((bcity=ccity)::int),4) br_city_eq_ccity, round(avg((bcity=tcity)::int),4) br_city_eq_txcity from b group by 1""")
# expected same-city under uniform branch draw within customer country
q("same-city observed vs expected (uniform branch within country) vs 1/ncities", """
with bc as (select country, city, count(*) nb from br group by all),
     tot as (select country, sum(nb) N, count(*) ncity from bc group by 1),
     obs as (select cc, ccity, count(*) n, avg((bcity=ccity)::int) same from b group by all)
select o.cc, sum(o.n) n, round(sum(o.n*o.same)/sum(o.n),4) obs_same,
  round(sum(o.n*coalesce(bc.nb,0)/tot.N)/sum(o.n),4) exp_uniform_branch, round(1.0/max(tot.ncity),4) inv_ncity
from obs o join tot on tot.country=o.cc left join bc on bc.country=o.cc and bc.city=o.ccity group by 1 order by 1""")
# branch-city share observed vs branch count share
q("branch city share in tx vs share of branches in br", """
with bc as (select country, city, count(*) nb from br group by all), tot as (select country, sum(nb) N from bc group by 1),
  o as (select bc country, bcity city, count(*) n from b group by all), ot as (select country, sum(n) T from o group by 1)
select o.country, o.city, o.n, round(o.n/ot.T,4) share_tx, round(bc.nb/tot.N,4) share_br from o join ot using(country) join bc using(country, city) join tot using(country) order by 1,2""")
# uniformity: chi-square of branch counts within customer country
for c in ['Argentina','Colombia','México']:
    cnt = con.execute(f"select b2.branch_id, count(b.transaction_id) n from br b2 left join b on b.branch_id=b2.branch_id and b.cc='{c}' where b2.country='{c}' group by 1").fetchnumpy()['n'].astype(float)
    chi = stats.chisquare(cnt)
    print(f"{c}: branches={len(cnt)} min={cnt.min():.0f} max={cnt.max():.0f} mean={cnt.mean():.0f} cv={cnt.std()/cnt.mean():.4f} expected_cv_poisson={1/np.sqrt(cnt.mean()):.4f} chi2={chi.statistic:.1f} p={chi.pvalue:.3f}")
print()
# Cramer's V customer city x branch city (within country)
for c in ['Argentina','Colombia','México']:
    df = con.execute(f"select ccity, bcity, count(*) n from b where cc='{c}' and bcity is not null group by all").df()
    tab = df.pivot(index='ccity', columns='bcity', values='n').fillna(0).values
    chi2, p, dof, _ = stats.chi2_contingency(tab)
    V = np.sqrt(chi2/(tab.sum()*(min(tab.shape)-1)))
    print(f"{c}: Cramer V(customer city, branch city)={V:.4f} p={p:.3f} n={tab.sum():.0f}")
print()
# per-customer repeated branch: distinct/n vs expected under uniform random draw
q("per-customer branch repetition vs random", """
with nb as (select country, count(*) N from br group by 1),
 c as (select customer_id, cc, count(*) n, count(distinct branch_id) d from b where br_found is not null group by all having count(*) between 5 and 30)
select c.cc, count(*) ncust, round(avg(n),2) mean_n, round(avg(d),3) mean_distinct,
  round(avg(nb.N*(1-pow(1-1.0/nb.N, n))),3) expected_distinct_random
from c join nb on nb.country=c.cc group by 1 order by 1""")
q("tx before branch opened / at non-active branch", """select count(*) n, sum((ts::date < bopened)::int) before_open, round(avg((ts::date < bopened)::int),4) rate_before_open
  from b where br_found is not null""")
q("branch status x usage", """select bstatus, count(*) n from b where br_found is not null group by 1 order by 2 desc""")
q("br status counts", "select branch_status, count(*) n from br group by 1")
q("channel x branch_type", "select channel, btype, count(*) n from b where br_found is not null group by all order by 1,2")
