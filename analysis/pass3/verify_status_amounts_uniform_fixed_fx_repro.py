import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

print("== 1. nulos de amount_usd por moneda ==")
print(q("""select currency, count(*) n, sum((amount_usd is null)::int) n_null,
  round(avg((amount_usd is null)::int)*100,2) pct_null from tx group by 1 order by 1""").to_string())
print(q("select round(avg((amount_usd is null)::int)*100,2) pct_null_total from tx").to_string())

print("== 2. coincidencia con tasa fija ==")
print(q("""select currency, count(*) n_nonnull,
  sum((abs(amount_usd - round(amount/case currency when 'COP' then 4000 when 'ARS' then 350 end,2))<0.0051)::int) match_fixed_round,
  sum((abs(amount_usd - amount/case currency when 'COP' then 4000 when 'ARS' then 350 end)<0.0051)::int) match_fixed_tol,
  min(amount/amount_usd) min_ratio, max(amount/amount_usd) max_ratio,
  sum((amount_usd < 0.5)::int) small_usd
  from tx where amount_usd is not null group by 1""").to_string())
# ratio restricted to amount_usd>=1 to avoid rounding noise
print(q("""select currency, min(amount/amount_usd) mn, max(amount/amount_usd) mx, count(*) n
  from tx where amount_usd>=1 group by 1""").to_string())

print("== 3. tabla fx ==")
print(q("select src,dst,count(*) n, min(rate) mn, avg(rate) av, max(rate) mx, min(date) d0, max(date) d1 from fx group by 1,2 order by 1,2").to_string())

print("== 4. coincidencia con tasa diaria fx ==")
for cur in ['COP','ARS']:
    r = q(f"""with f as (select date, rate from fx where src='USD' and dst='{cur}'),
    f2 as (select date, rate from fx where src='{cur}' and dst='USD')
    select count(*) n,
      sum((abs(t.amount_usd - round(t.amount/f.rate,2))<0.0051)::int) match_usd_to_cur,
      sum((abs(t.amount_usd - round(t.amount*f2.rate,2))<0.0051)::int) match_cur_to_usd,
      sum((abs(t.amount_usd - t.amount/f.rate) <= 0.01*t.amount_usd)::int) within1pct,
      corr(t.amount/t.amount_usd, f.rate) corr_ratio_rate,
      avg(f.rate) avg_rate
    from tx t join f on f.date = cast(t.ts as date) left join f2 on f2.date=cast(t.ts as date)
    where t.currency='{cur}' and t.amount_usd>=1""")
    print(cur); print(r.to_string())
    r = q(f"""with f as (select date, rate from fx where src='USD' and dst='{cur}')
    select count(*) n, sum((abs(t.amount_usd - round(t.amount/f.rate,2))<0.0051)::int) match_procdate
    from tx t join f on f.date = t.process_date where t.currency='{cur}' and t.amount_usd>=1""")
    print(r.to_string())

print("== 5. min/max por ttype y moneda, en USD-equivalente ==")
r = q("""select ttype, currency, count(*) n, min(amount) mn, max(amount) mx,
  min(amount)/case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end mn_usd,
  max(amount)/case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end mx_usd,
  sum((amount<0)::int) neg, sum((amount=0)::int) zero,
  sum((round(amount,2)<>amount)::int) not_cents
  from tx group by 1,2 order by 1,2""")
print(r.to_string())

print("== 6. KS vs Uniforme(a,b) por ttype en USD, y sobre USD-equivalente de COP/ARS (muestra) ==")
bounds = {'Purchase':(5,500),'Withdrawal':(20,500),'Payment':(50,2000),'Deposit':(50,5000),'Transfer':(100,10000),'Adjustment':(10,1000)}
for cur, k in [('USD',1),('COP',4000),('ARS',350)]:
    for tt,(a,b) in bounds.items():
        x = con.execute(f"select amount/{k} from tx where currency='{cur}' and ttype='{tt}' using sample reservoir(20000 rows) repeatable (7)").fetchnumpy()
        x = list(x.values())[0].astype(float)
        D,p = stats.kstest(x, 'uniform', args=(a,b-a))
        out = ((x<a)|(x>b)).sum()
        # decile balance
        print(f"{cur} {tt:10s} n={len(x):6d} min={x.min():.2f} max={x.max():.2f} KS D={D:.4f} p={p:.3f} fuera={out}")

print("== 7. ¿uniformidad depende de status? (media relativa (x-a)/(b-a) por status, todas las monedas) ==")
r = q("""with t as (select *, amount/case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end u from tx),
b as (select * from (values ('Purchase',5,500),('Withdrawal',20,500),('Payment',50,2000),('Deposit',50,5000),('Transfer',100,10000),('Adjustment',10,1000)) v(ttype,a,bb))
select status, count(*) n, round(avg((u-a)/(bb-a)),4) mean_rel, round(stddev((u-a)/(bb-a)),4) sd_rel,
 sum(((u<a) or (u>bb))::int) fuera
from t join b using(ttype) group by 1 order by 1""")
print(r.to_string())
