import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchall()
caps = {'Purchase':(5,500),'Withdrawal':(20,500),'Payment':(50,2000),'Deposit':(50,5000),'Transfer':(100,10000),'Adjustment':(10,1000)}
rate = {'USD':1,'COP':4000,'ARS':350}
print("== KS large samples (normalized to USD via fixed rate) ==")
for cur in ['USD','COP','ARS']:
    for t,(a,b) in caps.items():
        x = con.execute(f"select amount/{rate[cur]} from tx where currency='{cur}' and ttype='{t}' and hash(transaction_id)%10<2").fetchnumpy()
        x = list(x.values())[0]
        x = x[:120000]
        D,p = stats.kstest(x, 'uniform', args=(a,b-a))
        # decile chi2
        h,_ = np.histogram(x, bins=20, range=(a,b)); chi = stats.chisquare(h)
        print(cur,t,len(x),'KS D=%.4f p=%.3f'%(D,p),'chi20 p=%.3f'%chi.pvalue, 'min %.2f max %.2f'%(x.min(),x.max()))
print("== normalized amount (u=(usd-a)/(b-a)) mean by status/code/fraud/channel/country ==")
case = " ".join([f"when '{t}' then (amount/(case currency when 'USD' then 1 when 'COP' then 4000 else 350 end) - {a})/{b-a}" for t,(a,b) in caps.items()])
u = f"(case ttype {case} end)"
for col in ['status','code','fraud','channel','currency']:
    for r in q(f"select {col}, count(*), round(avg({u}),4), round(stddev({u}),4), round(min({u}),4), round(max({u}),4) from tx group by 1 order by 1"): print(col, r)
print("== fraud score bins ==")
for r in q(f"select case when fscore is null then -1 when fscore>=50 then 50 else 0 end b, count(*), round(avg({u}),4) from tx group by 1 order by 1"): print(r)
print("== Mexico: product currency ==")
for r in q("select c.country, p.currency, count(*) from pr p join cu c using(customer_id) group by 1,2 order by 1,2"): print(r)
print("== decimals: amounts with exactly 2 decimals? ==")
for r in q("select currency, round(avg((abs(amount*100 - round(amount*100))<1e-6)::int),4) from tx group by 1"): print(r)
print("== per-customer: amount related to income/segment? corr u vs income ==")
for r in q(f"""select corr(u, income), count(*) from (select {u} u, c.income from tx t join cu c using(customer_id) where hash(transaction_id)%20=0)"""): print(r)
for r in q(f"""select c.segment, count(*), round(avg({u}),4) from tx t join cu c using(customer_id) where hash(transaction_id)%20=0 group by 1 order by 1"""): print(r)
