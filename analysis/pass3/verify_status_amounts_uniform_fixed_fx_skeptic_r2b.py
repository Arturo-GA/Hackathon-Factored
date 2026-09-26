# Verificador escéptico r2b: uniformidad con TODOS los datos (histograma 1000 bins por moneda x ttype), topes, decimales
import duckdb, time, numpy as np, pandas as pd
from scipy import stats
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
def q(s):
    print(con.execute(s).df().to_string(), '\n', flush=True)

print("== 1. min/max/decimales por moneda x ttype (en moneda original y en USD-equivalente a tasa fija) ==")
q("""select currency, ttype, count(*) n, min(amount) mn, max(amount) mx,
      round(min(amount)/(case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end),4) mn_usd,
      round(max(amount)/(case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end),4) mx_usd,
      round(100*avg((abs(amount*100 - round(amount*100)) < 1e-6)::int),2) pct_2dec,
      round(100*avg((amount = round(amount))::int),2) pct_entero,
      sum((amount <= 0)::int) no_pos
    from tx group by 1,2 order by 2,1""")

B = {'Purchase':(5,500),'Withdrawal':(20,500),'Payment':(50,2000),'Deposit':(50,5000),'Transfer':(100,10000),'Adjustment':(10,1000)}
K = {'USD':1.0,'COP':4000.0,'ARS':350.0}
bexpr = "case ttype " + " ".join(f"when '{t}' then {a}" for t,(a,b) in B.items()) + " end"
wexpr = "case ttype " + " ".join(f"when '{t}' then {b-a}" for t,(a,b) in B.items()) + " end"
kexpr = "case currency when 'COP' then 4000.0 when 'ARS' then 350.0 else 1.0 end"
U = f"((amount/{kexpr} - {bexpr})/{wexpr})"

print("== 2. fuera de topes (en USD-equivalente) ==")
q(f"select currency, ttype, sum(({U} < 0)::int) bajo_min, sum(({U} > 1)::int) sobre_max, count(*) n from tx group by 1,2 having sum(({U}<0 or {U}>1)::int)>0 order by 1,2")

print("== 3. histograma 1000 bins, datos completos: chi2 (50 y 1000 bins) y D de KS por bins ==")
h = con.execute(f"select currency, ttype, least(999, greatest(0, floor({U}*1000)))::int b, count(*) c from tx group by all").df()
rows = []
for (cur, tt), g in h.groupby(['currency','ttype']):
    cnt = np.zeros(1000); cnt[g.b.values] = g.c.values
    n = cnt.sum()
    c50 = cnt.reshape(50, 20).sum(1)
    chi50 = stats.chisquare(c50); chi1000 = stats.chisquare(cnt)
    ecdf = np.cumsum(cnt)/n; cdf = np.arange(1, 1001)/1000
    D = np.abs(ecdf - cdf).max()
    pks = stats.kstwo.sf(D, int(n))
    # max desviacion relativa por decil
    dec = cnt.reshape(10, 100).sum(1)/n*10
    rows.append(dict(cur=cur, ttype=tt, n=int(n), chi50_p=round(chi50.pvalue,4), chi1000_p=round(chi1000.pvalue,4),
                     D_bins=round(D,5), D_crit95=round(1.358/np.sqrt(n),5), p_ks_aprox=round(pks,4),
                     dec_min=round(dec.min(),4), dec_max=round(dec.max(),4)))
r = pd.DataFrame(rows).sort_values(['ttype','cur'])
print(r.to_string(), '\n')
print("comparaciones: 18; umbral Bonferroni p<", round(0.05/18,4))
print(f"[t={time.time()-t0:.0f}s]")

print("== 4. primeros/ultimos bins (efecto borde: ¿redondeo o topes distintos?) USD-equiv, todas las monedas ==")
hh = con.execute(f"select ttype, least(999, greatest(0, floor({U}*1000)))::int b, count(*) c from tx group by all").df()
for tt, g in hh.groupby('ttype'):
    cnt = np.zeros(1000); cnt[g.b.values] = g.c.values
    m = cnt.mean()
    print(tt, "bins 0-2:", (cnt[:3]/m).round(3), " bins 997-999:", (cnt[-3:]/m).round(3))
print(f"[t={time.time()-t0:.0f}s]")
