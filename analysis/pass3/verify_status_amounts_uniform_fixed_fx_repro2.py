import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
K = "case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end"
print("== A. desajustes al redondear amount/k a centavos ==")
print(q(f"""select currency, count(*) n_mis, min(abs(amount_usd-amount/{K})) mind, max(abs(amount_usd-amount/{K})) maxd,
 max(abs(amount_usd-round(amount/{K},2))) max_diff_round
 from tx where amount_usd is not null and abs(amount_usd - round(amount/{K},2))>0.0001 group by 1""").to_string())
print(q(f"""select currency, max(abs(amount_usd-amount/{K})) max_abs_err, sum((round(amount_usd,2)<>amount_usd)::int) usd_not_cents
 from tx where amount_usd is not null group by 1""").to_string())

print("== B. precisión tabla fx (valores distintos COP->USD) ==")
print(q("select count(distinct rate) nd, sum((rate=0.00025)::int) n_eq from fx where src='COP' and dst='USD'").to_string())
print(q("select rate, count(*) from fx where src='COP' and dst='USD' group by 1 order by 2 desc limit 5").to_string())

print("== C. nulos de amount_usd COP/ARS vs ttype/status/channel (tasa %) ==")
for col in ['ttype','status','channel']:
    print(q(f"""select {col}, count(*) n, round(avg((amount_usd is null)::int)*100,2) pct_null
     from tx where currency<>'USD' group by 1 order by 1""").to_string())

print("== D. topes por ttype x channel / ptype (USD-equivalente) ==")
print(q(f"""select t.ttype, t.channel, count(*) n, round(min(amount/{K}),2) mn, round(max(amount/{K}),2) mx
 from tx t group by 1,2 having count(*)>1000 order by 1,2""").to_string())
print(q(f"""select t.ttype, p.ptype, count(*) n, round(min(t.amount/{K.replace('currency','t.currency')}),2) mn, round(max(t.amount/{K.replace('currency','t.currency')}),2) mx,
 round(avg((t.amount/{K.replace('currency','t.currency')})),1) mean
 from tx t join pr p using(product_id) group by 1,2 having count(*)>5000 order by 1,2""").to_string())

print("== E. KS con muestras grandes (sampling en subconsulta) ==")
bounds = {'Purchase':(5,500),'Withdrawal':(20,500),'Payment':(50,2000),'Deposit':(50,5000),'Transfer':(100,10000),'Adjustment':(10,1000)}
for cur, k in [('USD',1),('COP',4000),('ARS',350)]:
    for tt,(a,b) in bounds.items():
        x = con.execute(f"select u from (select amount/{k} u from tx where currency='{cur}' and ttype='{tt}') using sample reservoir(60000 rows) repeatable (11)").fetchnumpy()['u'].astype(float)
        D,p = stats.kstest(x, 'uniform', args=(a,b-a))
        # chi2 20 bins
        h,_ = np.histogram(x, bins=20, range=(a,b)); chi = stats.chisquare(h)
        print(f"{cur} {tt:10s} n={len(x):6d} KS D={D:.4f} p={p:.3f}  chi2(19)={chi.statistic:.1f} p={chi.pvalue:.3f} maxbin/minbin={h.max()/h.min():.3f}")
