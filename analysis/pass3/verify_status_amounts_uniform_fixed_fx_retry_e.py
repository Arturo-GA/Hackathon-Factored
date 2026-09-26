"""Verificacion (retry) status_amounts_uniform_fixed_fx. Parte E: topes y uniformidad por ttype x moneda con DATOS COMPLETOS (KS exacto en SQL + chi2 100 bins)."""
import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
B = "(values ('Purchase',5,500),('Withdrawal',20,500),('Payment',50,2000),('Deposit',50,5000),('Transfer',100,10000),('Adjustment',10,1000)) v(ttype,a,b)"
K = "(case t.currency when 'COP' then 4000 when 'ARS' then 350 else 1 end)"
base = f"select t.ttype, t.currency, t.amount/{K} x, v.a, v.b from tx t join {B} using(ttype)"
print("== ttypes presentes:", con.execute("select ttype, count(*) from tx group by 1 order by 2 desc").fetchall())
# topes y momentos
res = con.execute(f"""with d as ({base})
 select ttype, currency, count(*) n, min(x) mn, max(x) mx, any_value(a) a, any_value(b) b,
   sum(case when x < a or x > b then 1 else 0 end) fuera,
   avg((x-a)/(b-a)) mean_u, stddev_samp((x-a)/(b-a)) sd_u
 from d group by 1,2 order by 1,2""").fetchall()
print("ttype | cur | n | min_usd | max_usd | a | b | fuera | mean_u | sd_u (esperado 0.5 / 0.2887)")
for r in res: print(f"{r[0]:10s} | {r[1]} | {r[2]:8d} | {r[3]:.4f} | {r[4]:.4f} | {r[5]} | {r[6]} | {r[7]} | {r[8]:.4f} | {r[9]:.4f}")
# min/max en moneda original
print("== min/max en moneda original")
for r in con.execute("select ttype, currency, min(amount), max(amount) from tx group by 1,2 order by 2,1").fetchall(): print(r)
# KS exacto con datos completos (ECDF por grupo via row_number)
ks = con.execute(f"""with d as ({base}),
 r as (select ttype, currency, least(greatest((x-a)/(b-a),0),1) F,
        row_number() over (partition by ttype, currency order by x) rn,
        count(*) over (partition by ttype, currency) n from d)
 select ttype, currency, any_value(n) n, max(greatest(rn/n - F, F - (rn-1)/n)) D from r group by 1,2 order by 1,2""").fetchall()
print("== KS datos completos vs U(a*k, b*k)")
for t,c,n,D in ks:
    p = stats.kstwobign.sf(D*np.sqrt(n))
    print(f"{t:10s} {c} n={n:8d} D={D:.5f} p={p:.4f} (D critico 5%={1.358/np.sqrt(n):.5f})")
# chi2 100 bins
print("== chi2 100 bins datos completos")
h = con.execute(f"""with d as ({base}) select ttype, currency, least(cast(floor((x-a)/(b-a)*100) as int),99) bin, count(*) c from d group by 1,2,3""").fetchall()
from collections import defaultdict
g = defaultdict(lambda: np.zeros(100))
for t,c,bn,cnt in h: g[(t,c)][bn] += cnt
for k in sorted(g):
    obs = g[k]; chi = stats.chisquare(obs)
    print(f"{k[0]:10s} {k[1]} chi2(99)={chi.statistic:.1f} p={chi.pvalue:.4f} max/min bin={obs.max()/obs.min():.3f}")
# Pool por ttype (todas las monedas convertidas) y total
print("== KS por ttype (monedas agrupadas, en USD a tasa fija)")
ks2 = con.execute(f"""with d as ({base}),
 r as (select ttype, least(greatest((x-a)/(b-a),0),1) F, row_number() over (partition by ttype order by x) rn, count(*) over (partition by ttype) n from d)
 select ttype, any_value(n) n, max(greatest(rn/n - F, F - (rn-1)/n)) D from r group by 1 order by 1""").fetchall()
for t,n,D in ks2: print(f"{t:10s} n={n:8d} D={D:.5f} p={stats.kstwobign.sf(D*np.sqrt(n)):.4f}")
