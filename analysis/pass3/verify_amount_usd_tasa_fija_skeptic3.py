import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
import pandas as pd
pd.set_option('display.width', 200); pd.set_option('display.max_columns', 30)
base = "from tx where currency in ('ARS','COP')"
for col in [] if True else ['status','channel','ttype','fraud','(fscore is null)','(merchant_name is null)','(lat is null)','(code is null)','country','year(ts)']:
    d = q(f"select {col} as k, count(*) n, avg(case when amount_usd is null then 1.0 else 0 end) nr {base} group by 1 order by 1")
    print(col, ' | '.join(f"{r.k}:{r.nr:.4f}(n={r.n})" for r in d.itertuples()))
d = q(f"select ntile(10) over (partition by currency order by amount) dec, amount_usd is null isn {base}")  if False else None
print(q(f"""with t as (select currency, amount, amount_usd, ntile(10) over (partition by currency order by amount) dcl {base})
 select currency, dcl, min(amount) amin, max(amount) amax, avg(case when amount_usd is null then 1.0 else 0 end) nr from t group by 1,2 order by 1,2"""))
# per customer variance
d = q(f"select customer_id, count(*) n, avg(case when amount_usd is null then 1.0 else 0 end) r {base} group by 1 having count(*)>=10")
p = d.r.mean()
print("clientes", len(d), "var obs", d.r.var(), "var esperada binomial", (p*(1-p)/d.n).mean())
# fx autocorr
f = q("select date, rate from fx where src='USD' and dst='ARS' order by date")
r = f.rate.values; print("fx USD->ARS lag1 autocorr", np.corrcoef(r[:-1], r[1:])[0,1], "rel dev range", (r/350-1).min(), (r/350-1).max())
f = q("select date, rate from fx where src='USD' and dst='COP' order by date")
r = f.rate.values; print("fx USD->COP lag1 autocorr", np.corrcoef(r[:-1], r[1:])[0,1], "rel dev range", (r/4000-1).min(), (r/4000-1).max())
f = q("select date, rate from fx where src='USD' and dst='MXN' order by date")
r = f.rate.values; print("fx USD->MXN lag1 autocorr", np.corrcoef(r[:-1], r[1:])[0,1], "median", np.median(r))
# error using fx daily rate
print(q("""select t.currency, count(*) n, median(abs(t.amount/f.rate - t.amount_usd)/t.amount_usd) med_relerr_fx,
  median(abs(t.amount/(case t.currency when 'ARS' then 350 else 4000 end) - t.amount_usd)/t.amount_usd) med_relerr_K,
  corr(t.amount/t.amount_usd, f.rate) corr_ratio_fx
  from tx t join fx f on f.src='USD' and f.dst=t.currency and f.date=cast(t.ts as date)
  where t.currency in ('ARS','COP') and t.amount_usd >= 1 group by 1"""))
# currency of products by customer country, and tx currency by customer country
print(q("""select c.country, p.currency, count(*) n from pr p join cu c using(customer_id) group by all order by all"""))
print(q("""select c.country, t.currency, count(*) n from tx t join cu c using(customer_id) group by all order by all"""))
# tx currency vs product currency
print(q("""select count(*) n, sum(case when t.currency<>p.currency then 1 else 0 end) mism from tx t join pr p using(product_id)"""))
