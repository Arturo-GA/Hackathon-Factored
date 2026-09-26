# Verificador escéptico r2d: naturaleza de la tabla fx (ruido iid? precisión de inversas) y utilidad del tope como validador (cp.claimed)
import duckdb, time, numpy as np, pandas as pd
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
def q(s):
    print(con.execute(s).df().to_string(), '\n', flush=True)

print("== 1. fx USD->COP/ARS: autocorrelacion lag1 (serie real ~1; ruido iid ~0), tendencia, forma del ruido ==")
for dst, K in [('COP',4000.0),('ARS',350.0),('MXN',17.0)]:
    s = con.execute(f"select date, rate from fx where src='USD' and dst='{dst}' order by date").df()
    x = s.rate.values/K - 1
    ac1 = np.corrcoef(x[1:], x[:-1])[0,1]
    yr = s.date.astype('datetime64[ns]').dt.year
    by = s.groupby(yr).rate.mean().round(2).to_dict()
    print(dst, "lag1=", round(ac1,4), "min/max desv %:", round(x.min()*100,3), round(x.max()*100,3),
          "media por año:", by, "sd%:", round(x.std()*100,3), "(uniforme ±2% => sd 1.155%)")
print()
print("== 2. precision de la inversa COP->USD (explica coincidencias espurias con la inversa) ==")
q("""select rate, count(*) dias from fx where src='COP' and dst='USD' group by 1 order by 2 desc limit 6""")
q("""select round(avg((rate = 0.00025)::int)*100,2) pct_dias_igual_1_4000 from fx where src='COP' and dst='USD'""")
print("== 3. consistencia interna fx: inversa y triangulacion (mismo dia) ==")
q("""with a as (select date, rate r from fx where src='USD' and dst='COP'), b as (select date, rate r from fx where src='COP' and dst='USD'),
      c as (select date, rate r from fx where src='USD' and dst='ARS'), d as (select date, rate r from fx where src='ARS' and dst='COP')
     select round(avg(abs(a.r*b.r-1))*100,3) err_inv_pct, round(avg(abs(c.r*d.r/a.r-1))*100,3) err_triang_pct
     from a join b using(date) join c using(date) join d using(date)""")

print("== 4. cp.claimed vs topes de tx (USD-equivalente a tasa fija) ==")
q("""select currency, count(*) n, count(claimed) con_monto, round(min(claimed),2) mn, round(median(claimed),2) med, round(max(claimed),2) mx,
      round(100*avg((claimed/(case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end) > 10000)::int),2) pct_sobre_10k,
      round(100*avg((claimed/(case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end) > 500)::int),2) pct_sobre_500
    from cp group by 1 order by 1""")
print("== 5. ¿el monto reclamado coincide con alguna tx del mismo cliente? (exacto y ±1%) ==")
q("""with c as (select complaint_id, customer_id, claimed, currency from cp where claimed is not null),
      m as (select c.complaint_id,
              max((abs(t.amount - c.claimed) < 0.005)::int) exacto,
              max((abs(t.amount - c.claimed) <= 0.01*c.claimed)::int) pm1
            from c join tx t on t.customer_id=c.customer_id and t.currency=c.currency group by 1)
     select (select count(*) from c) n_reclamos, count(*) con_tx_misma_moneda, sum(exacto) match_exacto, sum(pm1) match_1pct from m""")
print(f"[t={time.time()-t0:.0f}s]")
