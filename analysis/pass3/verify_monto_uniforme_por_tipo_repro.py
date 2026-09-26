import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: con.execute(s).df()
K="(case currency when 'ARS' then 350.0 when 'COP' then 4000.0 else 1.0 end)"
LO="(case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Payment' then 50 when 'Adjustment' then 10 when 'Deposit' then 50 else 100 end)"
HI="(case ttype when 'Purchase' then 500 when 'Withdrawal' then 500 when 'Payment' then 2000 when 'Adjustment' then 1000 when 'Deposit' then 5000 else 10000 end)"
con.execute(f"create temp view v as select *, amount/{K} a, (amount/{K}-{LO})/({HI}-{LO}) u from tx")
print("== dentro de limites (tolerancia 0.01 USD-eq)")
print(q(f"select count(*) n, sum((a>={LO}-0.01 and a<={HI}+0.01)::int) inside, sum((a>={LO} and a<={HI})::int) inside_strict from v").to_string())
print(q("select ttype, currency, min(a) mn, max(a) mx, avg(u) mu, stddev(u) sd from v group by 1,2 order by 1,2").to_string())
print("expected sd uniform:", 1/np.sqrt(12))
print("== chi2 20 bins por celda")
d=q("select ttype, currency, least(floor(u*20),19)::int b, count(*) n from v group by 1,2,3")
res=[]
for (t,c),g in d.groupby(['ttype','currency']):
    obs=g.set_index('b').n.reindex(range(20),fill_value=0).values
    exp=obs.sum()/20
    ch,p=stats.chisquare(obs)
    res.append((t,c,obs.sum(),round(ch,1),round(p,3),round(np.max(np.abs(obs/exp-1))*100,2)))
for r in res: print(r)
print("min p:",min(r[4] for r in res),"max dev%:",max(r[5] for r in res))
print("== KS en muestra 200k: uniforme vs log-uniforme")
s=q(f"select ttype, currency, a, u from v using sample 200000 rows")
lo={'Purchase':5,'Withdrawal':20,'Transfer':100,'Payment':50,'Deposit':50,'Adjustment':10}
hi={'Purchase':500,'Withdrawal':500,'Transfer':10000,'Payment':2000,'Deposit':5000,'Adjustment':1000}
for t,g in s.groupby('ttype'):
    du=stats.kstest(g.u,'uniform').statistic
    lu=(np.log(g.a)-np.log(lo[t]))/(np.log(hi[t])-np.log(lo[t]))
    dl=stats.kstest(lu,'uniform').statistic
    print(t,len(g),'D_unif=%.4f D_logunif=%.3f'%(du,dl))
print("== enteros y primer digito")
print(q("select avg((amount=round(amount))::int) frac_int, avg((amount*100=round(amount*100))::int) frac_2dec from v").to_string())
print(q("select avg((round(amount)<>amount)::int) cents from v where channel='ATM' and ttype='Withdrawal'").to_string())
print(q("select left(cast(floor(a) as varchar),1) d, count(*)*1.0/sum(count(*)) over () p from v where currency='USD' group by 1 order by 1").to_string())
