# Parte B: uniformidad fina en datos completos (1000 bins), KS aproximado vs valor crítico, y forma (media/var/asimetría)
import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
K="(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"
LO="(case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Transfer' then 100 when 'Payment' then 50 when 'Deposit' then 50 else 10 end)"
HI="(case ttype when 'Purchase' then 500 when 'Withdrawal' then 500 when 'Transfer' then 10000 when 'Payment' then 2000 when 'Deposit' then 5000 else 1000 end)"
U=f"((amount/{K} - {LO})/({HI}-{LO}))"
NB=1000
df=con.execute(f"select ttype, currency, least(floor({U}*{NB}),{NB-1})::int b, count(*) n from tx group by all").df()
print('== ttype x moneda: chi2 con 1000 bins, KS aprox (max |ECDF-u| en bordes de bin), crit 5% = 1.36/sqrt(n) ==')
rows=[]
for (t,c),g in df.groupby(['ttype','currency']):
    h=np.zeros(NB); h[g.b.values]=g.n.values
    n=h.sum(); chi=stats.chisquare(h)
    ecdf=np.cumsum(h)/n; D=np.max(np.abs(ecdf-np.arange(1,NB+1)/NB))
    rows.append((t,c,int(n),chi.statistic,chi.pvalue,D,1.36/np.sqrt(n), D*np.sqrt(n)))
    print(f"{t:11s} {c} n={int(n):7d} chi2(999)={chi.statistic:8.1f} p={chi.pvalue:.3f} D={D:.5f} crit={1.36/np.sqrt(n):.5f} sqrt(n)D={D*np.sqrt(n):.2f} p_KS={stats.kstwobign.sf(D*np.sqrt(n)):.3f}")
pv=np.array([r[4] for r in rows]); pk=np.array([stats.kstwobign.sf(r[7]) for r in rows])
print('min p chi2 =',pv.min().round(4),' min p KS =',pk.min().round(4),' (18 pruebas; Bonferroni 0.05/18=0.0028)')
# pooled by ttype
print('\n== por ttype (monedas juntas) ==')
for t,g in df.groupby('ttype'):
    gg=g.groupby('b').n.sum(); h=np.zeros(NB); h[gg.index.values]=gg.values; n=h.sum()
    chi=stats.chisquare(h); ecdf=np.cumsum(h)/n; D=np.max(np.abs(ecdf-np.arange(1,NB+1)/NB))
    print(f"{t:11s} n={int(n):7d} chi2={chi.statistic:8.1f} p={chi.pvalue:.3f} D={D:.5f} p_KS={stats.kstwobign.sf(D*np.sqrt(n)):.3f}")
print('\n== momentos de u por ttype x moneda (uniforme: media .5, var .08333, asim 0, curtosis exceso -1.2) ==')
q(f"""select ttype, currency, count(*) n, avg(u) mean_u, var_samp(u) var_u, skewness(u) skew, kurtosis(u) exkurt, min(u) mn, max(u) mx
 from (select ttype, currency, {U} u from tx) group by all order by 1,2""")
# log-uniform alternative check at full data: fraction below midpoint in log scale
print('== alternativa log-uniforme: fraccion de montos bajo la media geometrica sqrt(lo*hi) (log-unif => 0.5; unif => (sqrt(lo*hi)-lo)/(hi-lo)) ==')
q(f"""select ttype, count(*) n, avg((amount/{K} < sqrt({LO}*{HI}))::int) frac_below_gm, any_value((sqrt({LO}*{HI})-{LO})/({HI}-{LO})) expected_unif from tx group by 1 order by 1""")
