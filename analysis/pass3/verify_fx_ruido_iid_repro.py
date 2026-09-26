import duckdb, numpy as np, pandas as pd
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: con.execute(s).df()
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
fx = q("select * from fx")
print(fx.shape, fx.dtypes.to_dict())
print(fx.groupby(['src','dst']).size().unstack())
print('dates', fx.date.min(), fx.date.max(), fx.date.nunique())
print('dup (date,src,dst):', fx.duplicated(['date','src','dst']).sum())
print(fx.source.value_counts())
# per pair stats
g = fx.groupby(['src','dst']).rate
print(pd.DataFrame({'min':g.min(),'med':g.median(),'max':g.max(),'mean':g.mean(),'cv%':g.std()/g.mean()*100}).to_string())
# relative deviation from median: uniform? distribution shape
fx['dev'] = fx.rate/fx.groupby(['src','dst']).rate.transform('median')-1
print('dev range', fx.dev.min(), fx.dev.max(), 'sd', fx.dev.std())
print('dev quantiles', fx.dev.quantile([0,.01,.1,.25,.5,.75,.9,.99,1]).round(4).tolist())
# yearly means for USD->*
fx['y']=pd.to_datetime(fx.date).dt.year
print(fx[fx.src=='USD'].pivot_table(index='y',columns='dst',values='rate',aggfunc='mean').round(3))
# linear trend per pair: slope over the full period (% total change)
for (s,d),sub in fx.groupby(['src','dst']):
    sub=sub.sort_values('date'); t=(pd.to_datetime(sub.date)-pd.Timestamp('2023-06-17')).dt.days.values
    b=np.polyfit(t,sub.rate.values,1); tot=b[0]*t.max()/sub.rate.mean()*100
    r=sub.rate.values; ac1=np.corrcoef(r[1:],r[:-1])[0,1]; ret=r[1:]/r[:-1]-1
    print(f"{s}->{d}: trend_total%={tot:.3f}  ac1={ac1:.3f}  sd_dailychg%={ret.std()*100:.2f}  ndec_sig={sub.rate.astype(str).str.len().median()}")
# inverse consistency
p = fx.pivot_table(index='date',columns=['src','dst'],values='rate')
pairs=[('USD','MXN'),('USD','COP'),('USD','ARS'),('MXN','COP'),('MXN','ARS'),('COP','ARS')]
for a,b in pairs:
    prod=p[(a,b)]*p[(b,a)]
    print(f"{a}<->{b}: prod mean={prod.mean():.4f} sd%={prod.std()*100:.2f} min={prod.min():.4f} max={prod.max():.4f}")
    # correlation between A->B and 1/(B->A): if consistent, corr ~1
    print('    corr(rate, 1/inv)=', round(np.corrcoef(p[(a,b)],1/p[(b,a)])[0,1],3))
# triangular
tri = p[('USD','ARS')]/(p[('USD','MXN')]*p[('MXN','ARS')])
print('tri USD->ARS vs USD->MXN*MXN->ARS: mean', tri.mean(), 'sd%', tri.std()*100, tri.min(), tri.max())
tri2 = p[('USD','COP')]/(p[('USD','ARS')]*p[('ARS','COP')])
print('tri USD->COP vs USD->ARS*ARS->COP: mean', tri2.mean(), 'sd%', tri2.std()*100)
# cross-pair correlation of daily deviations (common factor?)
dev = p/p.median()-1
c = dev.corr().values; iu=np.triu_indices_from(c,1)
print('cross-pair corr of deviations: mean', c[iu].mean().round(3), 'maxabs', np.abs(c[iu]).max().round(3))
# buy/sell
fx['spread']=(fx.sell-fx.buy)/fx.rate
print('buy<rate<sell', ((fx.buy<fx.rate)&(fx.rate<fx.sell)).mean(), 'spread mean', fx.spread.mean(), fx.spread.min(), fx.spread.max())
print('buy side %', ((fx.rate-fx.buy)/fx.rate).describe().round(4).to_dict())
print('sell side %', ((fx.sell-fx.rate)/fx.rate).describe().round(4).to_dict())
# source vs pair/date independence
ct = pd.crosstab(fx.source, fx.src+'>'+fx.dst)
from scipy.stats import chi2_contingency
chi,pv,_,_ = chi2_contingency(ct); V=np.sqrt(chi/(ct.values.sum()*(min(ct.shape)-1)))
print('source x pair V', round(V,3), 'p', pv)
# does source relate to deviation?
print(fx.groupby('source').dev.agg(['mean','std']).round(5))
# Same source across 12 pairs within a day?
print('mean #distinct sources per date', fx.groupby('date').source.nunique().mean())
# COP->USD sig digits
cu = fx[(fx.src=='COP')&(fx.dst=='USD')].rate
print('COP->USD distinct', cu.nunique(), cu.min(), cu.max(), cu.head(5).tolist())
for (s,d),sub in fx.groupby(['src','dst']):
    print(s,d,'distinct',sub.rate.nunique(), 'sample', sub.rate.head(3).tolist())
# Compare with tx implied rate amount/amount_usd
print(q("""select currency, count(*) n, median(amount/amount_usd) med, quantile_cont(amount/amount_usd,0.01) p01, quantile_cont(amount/amount_usd,0.99) p99
 from tx where amount_usd is not null and amount_usd>=1 group by all"""))
print(q("""select currency, avg((abs(amount_usd - amount/(case currency when 'ARS' then 350 when 'COP' then 4000 end))<=0.005001)::int) fixed_match, count(*) n
 from tx where amount_usd is not null and currency<>'USD' group by all"""))
print(q("""with t as (select currency, cast(ts as date) d, amount, amount_usd from tx where amount_usd is not null and currency<>'USD')
 select currency, count(*) n, avg((abs(amount_usd - amount/f.rate)<=0.005001)::int) fx_day_match, median(abs(amount/amount_usd/f.rate-1)) med_relerr
 from t join fx f on f.date=t.d and f.src='USD' and f.dst=t.currency group by all"""))
# noise shape vs central fixed rates
from scipy.stats import kstest
C={'USD':1.0,'MXN':17.0,'ARS':350.0,'COP':4000.0}
fx['u']=fx.rate/(fx.dst.map(C)/fx.src.map(C))-1
print('u vs fixed center: min %.4f max %.4f mean %.5f sd %.4f' % (fx.u.min(),fx.u.max(),fx.u.mean(),fx.u.std()))
big=fx[fx.rate>1]
print('KS uniform(-0.02,0.02) on pairs with rate>1:', kstest(big.u,'uniform',args=(-0.02,0.04)))
print('KS normal:', kstest(big.u/big.u.std(),'norm'))
print('weekend share of dates', (pd.to_datetime(fx.date.drop_duplicates()).dt.dayofweek>=5).mean())
