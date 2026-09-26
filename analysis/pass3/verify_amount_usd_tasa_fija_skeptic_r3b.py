# Verificador escéptico (r3b): tabla fx vs K; moneda por país/producto; escala de montos
import duckdb, time, numpy as np
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
import pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
def q(s, show=True):
    df = con.execute(s).df()
    if show: print(df.to_string(), '\n', flush=True)
    return df

print("== 5. fx: nivel y dispersion relativa a K ==")
q("""select src, dst, count(*) n, min(date) d0, max(date) d1, round(median(rate),3) med, round(avg(rate),3) mean, round(stddev(rate),3) sd,
   round(min(rate),3) mn, round(max(rate),3) mx,
   round(median(abs(rate/(case when dst='ARS' then 350 when dst='COP' then 4000 end)-1)),5) med_absrel_vsK,
   round(max(abs(rate/(case when dst='ARS' then 350 when dst='COP' then 4000 end)-1)),5) max_absrel_vsK,
   sum((rate=350 or rate=4000)::int) n_exact_K,
   round(corr(rate, epoch(date)),4) corr_trend
   from fx where src='USD' and dst in ('ARS','COP','MXN') group by all order by 1,2""")
q("""select src, dst, year(date) y, round(median(rate),3) med, round(stddev(rate)/avg(rate),5) cv from fx
   where src='USD' and dst in ('ARS','COP') group by all order by all""")
# inversos X->USD
q("""select src, dst, round(median(1/rate),3) med_inv, round(median(abs((1/rate)/(case when src='ARS' then 350 when src='COP' then 4000 end)-1)),5) med_absrel_vsK
   from fx where dst='USD' and src in ('ARS','COP') group by all""")
# autocorrelacion lag-1 de los retornos/niveles
for dst, K in [('ARS',350),('COP',4000),('MXN',None)]:
    f = q(f"select date, rate from fx where src='USD' and dst='{dst}' order by date", show=False)
    r = f.rate.values
    print(dst, "lag1 autocorr nivel", round(np.corrcoef(r[:-1], r[1:])[0,1],4), "n", len(r))
print()
print("== 6. ¿algun rezago de fx reproduce el cociente? (filas amount_usd>=50, muestra) ==")
con.execute("""create temp table s as select currency, ts::date d, amount/amount_usd ratio, amount, amount_usd from tx
   where amount_usd >= 50 and currency in ('ARS','COP') using sample 200000 rows""")
res = []
for lag in [-30,-7,-1,0,1,7,30]:
    d = q(f"""select s.currency, {lag} lag, count(*) n, corr(s.ratio, f.rate) corr_ratio_fx,
          median(abs(s.amount/f.rate/s.amount_usd-1)) med_relerr_fx,
          avg((abs(s.amount/f.rate/s.amount_usd-1) < 1e-4)::int) hit_fx,
          median(abs(s.ratio/(case s.currency when 'ARS' then 350 else 4000 end)-1)) med_relerr_K
          from s join fx f on f.src='USD' and f.dst=s.currency and f.date = s.d + {lag} group by all""", show=False)
    res.append(d)
print(pd.concat(res).sort_values(['currency','lag']).to_string(), '\n')
print(f"[t={time.time()-t0:.0f}s]")

print("== 7. moneda por pais del cliente: productos y transacciones ==")
q("select c.country, p.currency, count(*) n from pr p join cu c using(customer_id) group by all order by all")
q("select c.country, t.currency, count(*) n from tx t join cu c using(customer_id) group by all order by all")
q("select count(*) n, sum((t.currency<>p.currency)::int) mismatch_ccy from tx t join pr p using(product_id)")
print("-- share USD por tipo de producto (AR/CO) --")
d = q("""select c.country, p.ptype, count(*) n, round(avg((p.currency='USD')::int),4) usd_share
   from pr p join cu c using(customer_id) where c.country not in (select country from cu group by country having count(*)=0) group by all order by all""", show=False)
print(d.to_string(), '\n')
print("-- clientes AR/CO: productos locales y USD a la vez --")
q("""with x as (select p.customer_id, c.country, max((p.currency='USD')::int) has_usd, min((p.currency='USD')::int) all_usd, count(*) np
    from pr p join cu c using(customer_id) group by all)
    select country, count(*) clientes, round(avg(has_usd),4) con_algun_usd, round(avg(all_usd),4) todos_usd, round(avg(np),2) prod_por_cliente from x group by 1 order by 1""")
print(f"[t={time.time()-t0:.0f}s]")

print("== 8. escala: amount/K por moneda y tipo de tx (¿mismo generador en USD?) ==")
q("""select ttype, currency, count(*) n,
   round(quantile_cont(amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end),0.10),2) p10,
   round(median(amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)),2) p50,
   round(quantile_cont(amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end),0.90),2) p90,
   round(min(amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)),2) mn,
   round(max(amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)),2) mx
   from tx group by all order by 1,2""")
print(f"[t={time.time()-t0:.0f}s]")
