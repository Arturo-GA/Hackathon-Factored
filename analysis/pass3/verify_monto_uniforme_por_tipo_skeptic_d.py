# Parte D: efecto cliente/producto (F con TODOS los clientes), dependencia secuencial, repeticiones exactas de monto, y rechazo/código/fraude vs u
import duckdb, numpy as np, pandas as pd
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
K="(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"
LO="(case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Transfer' then 100 when 'Payment' then 50 when 'Deposit' then 50 else 10 end)"
HI="(case ttype when 'Purchase' then 500 when 'Withdrawal' then 500 when 'Transfer' then 10000 when 'Payment' then 2000 when 'Deposit' then 5000 else 1000 end)"
U=f"((amount/{K} - {LO})/({HI}-{LO}))"
print('== 1) efecto cliente / producto / cliente x ttype: F = var entre grupos / var esperada iid (1/12). Todos los grupos ==')
for key in ['customer_id','product_id','customer_id, ttype']:
    r=con.execute(f"""with g as (select {key}, count(*) n, avg({U}) m from tx group by all)
      select count(*) G, sum(n) N, sum(n*(m-0.5)*(m-0.5)) SSB from g""").fetchone()
    G,N,SSB=r; df1=G-1; F=(SSB/df1)/(1/12)
    print(f"{key:18s} grupos={G:7d} N={N} F={F:.4f} p={stats.chi2.sf(SSB*12,df1):.3f}  eta2~{SSB*12/N:.5f} (esperado nulo ~{df1/N:.5f})")
print('\n== 2) dependencia secuencial dentro de producto (orden ts) ==')
q(f"""with s as (select product_id, ttype, ts, {U} u, lag({U}) over w pu, lag(ttype) over w pt, epoch(ts)-epoch(lag(ts) over w) gap, status, lag(status) over w pst
   from tx window w as (partition by product_id order by ts, transaction_id))
 select count(*) n, corr(u,pu) r_lag1, corr(u,pu) filter (where pt=ttype) r_lag1_same_type, corr(u, ln(gap+1)) r_u_loggap,
   avg(u) filter (where pst='Declined') mean_u_after_decl, avg(u) filter (where pst='Approved') mean_u_after_appr,
   corr(u,pu) filter (where pst='Declined' and pt=ttype) r_after_decl_same_type, count(*) filter (where pst='Declined' and pt=ttype) n_after_decl
 from s where pu is not null""")
print('== 3) montos exactamente repetidos dentro de producto x ttype vs esperado por azar (dada la distribucion de montos por moneda x ttype) ==')
obs=con.execute("""with a as (select product_id, ttype, currency, amount, count(*) c from tx group by all)
  select sum(c*(c-1)/2) from a""").fetchone()[0]
pa=con.execute("""with f as (select currency, ttype, amount, count(*) c from tx group by all), t as (select currency, ttype, sum(c) tot from f group by all)
  select f.currency, f.ttype, sum(c*(c-1.0))/(any_value(tot)*(any_value(tot)-1.0)) p2 from f join t using(currency, ttype) group by all""").df()
npt=con.execute("select currency, ttype, sum(n*(n-1)/2) pairs from (select product_id, ttype, currency, count(*) n from tx group by all) group by all").df()
m=npt.merge(pa,on=['currency','ttype']); exp=(m.pairs*m.p2).sum()
print(f"pares con monto identico: observados={obs:.0f} esperados_azar={exp:.1f} razon={obs/exp:.3f} p_poisson_2colas={2*min(stats.poisson.cdf(obs,exp),stats.poisson.sf(obs-1,exp)):.3g}")
print(m.assign(exp=m.pairs*m.p2).groupby("currency").exp.sum().round(1).to_dict())
# same amount within 7 days after a Declined/Reversed/Pending (retry/refund) vs Approved
q("""with s as (select product_id, status, amount, ts, lead(amount) over w na, lead(status) over w nst, epoch(lead(ts) over w)-epoch(ts) gap
   from tx window w as (partition by product_id order by ts, transaction_id))
 select status, count(*) n, sum((na=amount)::int) next_same_amount, avg((abs(na/amount-1)<0.01)::int) next_within_1pct from s where na is not null group by 1 order by 1""")
print('== 4) resultado vs u: AUC (Mann-Whitney) de u para Declined, code 51, fraude; por quintil ==')
q(f"""select floor({U}*5)::int q, count(*) n, round(100*avg((status='Declined')::int),3) decl_pct, round(100*avg((code='51')::int),3) c51_pct,
  round(100*avg((code is not null and code<>'00')::int),3) code_rech_pct, round(1000*avg(fraud::int),3) fraud_pm from tx group by 1 order by 1""")
df=con.execute(f"select customer_id, {U} u, (status='Declined')::int decl, coalesce(code='51',false)::int c51, fraud::int fr, ttype from tx using sample 300000 rows").df()
rng=np.random.default_rng(1)
cust=df.customer_id.astype('category').cat.codes.values; nc=cust.max()+1
def auc(y,x):
    return stats.mannwhitneyu(x[y==1],x[y==0]).statistic/((y==1).sum()*(y==0).sum())
for col in ['decl','c51','fr']:
    y=df[col].values; x=df.u.values; a=auc(y,x); bs=[]
    for _ in range(200):
        cs=rng.integers(0,nc,nc); w=np.bincount(cs,minlength=nc)  # bootstrap por cliente
        wt=w[cust]; idx=np.repeat(np.arange(len(y)),wt)
        bs.append(auc(y[idx],x[idx]))
    print(f"{col}: positivos={y.sum()} AUC(u)={a:.4f} IC95 cluster-boot=[{np.percentile(bs,2.5):.4f}, {np.percentile(bs,97.5):.4f}]")
print('== 5) repeticiones a nivel cliente x ttype en centavos USD-eq (pagos recurrentes entre productos) vs esperado en rejilla de centavos ==')
q(f"""with v as (select customer_id, ttype, round(amount/{K},2) ra, {LO} lo, {HI} hi from tx),
 g as (select customer_id, ttype, ra, count(*) c from v group by all),
 cnt as (select customer_id, ttype, any_value(lo) lo, any_value(hi) hi, count(*) n from v group by all)
 select (select sum(c*(c-1)/2) from g) obs_pairs, (select sum(n*(n-1)/2/((hi-lo)*100.0+1)) from cnt) exp_pairs""")
