# Verificador escéptico (r3e): forma del ruido de fx alrededor de K; sd del cociente
import duckdb, pandas as pd
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
q = lambda s: print(con.execute(s).df().to_string(), '\n', flush=True)
print("== 13. cuantiles de rate/K-1 en fx (uniforme ±2% daria -1.6,-1,0,1,1.6 %) ==")
q("""select src, dst, count(*) n,
  round(100*quantile_cont(rate/K-1,0.10),3) p10, round(100*quantile_cont(rate/K-1,0.25),3) p25, round(100*quantile_cont(rate/K-1,0.5),3) p50,
  round(100*quantile_cont(rate/K-1,0.75),3) p75, round(100*quantile_cont(rate/K-1,0.90),3) p90,
  round(100*median((sell-buy)/rate),3) spread_pct
  from (select *, case when dst='ARS' then 350.0 when dst='COP' then 4000.0 when dst='MXN' then 17.0 end K from fx where src='USD' and dst in ('ARS','COP','MXN'))
  group by all order by 1,2""")
print("== 14. cociente amount/amount_usd (todas las filas no nulas) ==")
q("""select currency, count(*) n, round(median(amount/amount_usd),4) med, round(stddev(amount/amount_usd),4) sd,
  round(min(amount/amount_usd),3) mn, round(max(amount/amount_usd),3) mx from tx where amount_usd is not null group by 1 order by 1""")
print("== 15. nulos USD por pais del cliente ==")
q("""select c.country, t.currency, count(*) n, count(t.amount_usd) no_nulos from tx t join cu c using(customer_id) group by all order by all""")
