import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
V="(select *, amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) a from tx)"
bounds={'Purchase':(5,500),'Withdrawal':(20,500),'Transfer':(100,10000),'Payment':(50,2000),'Deposit':(50,5000),'Adjustment':(10,1000)}
# rule consistency: fraction within bounds
q(f"""select ttype, count(*) n, avg((a>=case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Transfer' then 100 when 'Payment' then 50 when 'Deposit' then 50 else 10 end - 0.01
 and a<= case ttype when 'Purchase' then 500 when 'Withdrawal' then 500 when 'Transfer' then 10000 when 'Payment' then 2000 when 'Deposit' then 5000 else 1000 end + 0.01)::int) in_bounds from {V} group by all""")
df=con.execute(f"select ttype, currency, a from {V} using sample 200000 rows").df()
for t,(lo,hi) in bounds.items():
    x=df.loc[df.ttype==t,'a'].values
    ks=stats.kstest(x,'uniform',args=(lo,hi-lo))
    # log-uniform alternative
    ksl=stats.kstest(np.log(x),'uniform',args=(np.log(lo),np.log(hi)-np.log(lo)))
    # decile counts
    h,_=np.histogram(x,bins=10,range=(lo,hi))
    print(t,len(x),'KS uniform D=%.4f p=%.3g | KS loguniform D=%.4f'%(ks.statistic,ks.pvalue,ksl.statistic),'deciles',np.round(h/len(x),3))
# first digit Benford
print()
for cur in ['USD','ARS','COP']:
    x=con.execute(f"select cast(substr(cast(cast(floor(amount) as bigint) as varchar),1,1) as int) d, count(*) n from tx where currency='{cur}' and amount>=1 group by 1 order by 1").fetchall()
    tot=sum(n for _,n in x)
    print(cur,'first digit share',[ (d, round(n/tot,3)) for d,n in x])
print('Benford',[round(np.log10(1+1/d),3) for d in range(1,10)])
# decimals / round numbers
q("""select currency, count(*) n, avg((amount=floor(amount))::int) whole, avg((amount % 10 = 0)::int) mult10, avg((amount % 100 = 0)::int) mult100,
 avg((round(amount*100)%10=0)::int) cent_last0 from tx group by all""")
q("""select currency, ttype, avg((amount=floor(amount))::int) whole, avg((amount%100=0)::int) m100 from tx group by all order by 1,2""")
