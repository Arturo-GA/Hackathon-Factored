import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
U="""((amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) - case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Transfer' then 100 when 'Payment' then 50 when 'Deposit' then 50 else 10 end)
 / (case ttype when 'Purchase' then 495 when 'Withdrawal' then 480 when 'Transfer' then 9900 when 'Payment' then 1950 when 'Deposit' then 4950 else 990 end))"""
df=con.execute(f"select ttype, currency, least(floor({U}*20),19) b, count(*) n from tx group by all").df()
for (t,c),g in df.groupby(['ttype','currency']):
    h=g.sort_values('b').n.values
    chi=stats.chisquare(h)
    print(f"{t:11s} {c} n={h.sum():7d} chi2={chi.statistic:7.1f} p={chi.pvalue:.3g} maxdev={np.max(np.abs(h/h.mean()-1)):.3f}")
q("select currency, avg((abs(amount*100-round(amount*100))<1e-6)::int) two_dec from tx group by 1")
# ATM withdrawals with cents
q("select channel, ttype, avg((amount=floor(amount))::int) whole, count(*) n from tx where ttype='Withdrawal' and currency='USD' group by all")
