# Verificacion independiente (reintento) de "monto_uniforme_por_tipo" - parte 4: montos repetidos exactos (pares ocultos: reversos,
# transferencias espejo, pagos recurrentes) vs lo esperado por azar bajo Uniforme iid en la grilla de centavos
import duckdb, numpy as np, pandas as pd
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250)
q = lambda s: con.execute(s).df()
LO = {'Purchase': 5, 'Withdrawal': 20, 'Payment': 50, 'Adjustment': 10, 'Deposit': 50, 'Transfer': 100}
HI = {'Purchase': 500, 'Withdrawal': 500, 'Payment': 2000, 'Adjustment': 1000, 'Deposit': 5000, 'Transfer': 10000}
KV = {'ARS': 350, 'COP': 4000, 'USD': 1}

print("== 1) Pares con monto identico dentro de cada celda ttype x moneda (global) y dentro del mismo cliente")
g = q("""with d as (select ttype, currency, round(amount*100)::bigint c, count(*) k from tx group by all)
  select ttype, currency, sum(k) n, count(*) distintos, sum(k*(k-1)/2) pares_obs from d group by all order by 1,2""")
g['M'] = [(HI[t] - LO[t]) * KV[c] * 100 for t, c in zip(g.ttype, g.currency)]  # tamano efectivo de la grilla de centavos
g['pares_esp'] = g.n * (g.n - 1) / 2 / g.M
g['razon'] = g.pares_obs / g.pares_esp
cc = q("""with d as (select customer_id, ttype, currency, round(amount*100)::bigint c, count(*) k from tx group by all),
  s as (select ttype, currency, sum(k*(k-1)/2) pares_obs_cli from d group by all),
  n as (select customer_id, ttype, currency, count(*) k from tx group by all),
  e as (select ttype, currency, sum(k*(k-1)/2) pares_posibles_cli from n group by all)
  select * from s join e using(ttype, currency)""")
g = g.merge(cc, on=['ttype', 'currency'])
g['pares_esp_cli'] = g.pares_posibles_cli / g.M
g['razon_cli'] = g.pares_obs_cli / g.pares_esp_cli
print(g.to_string(index=False, float_format=lambda x: '%.4g' % x))
print("TOTAL global: obs=%d esp=%.1f razon=%.3f | mismo cliente: obs=%d esp=%.1f razon=%.3f" % (
    g.pares_obs.sum(), g.pares_esp.sum(), g.pares_obs.sum() / g.pares_esp.sum(),
    g.pares_obs_cli.sum(), g.pares_esp_cli.sum(), g.pares_obs_cli.sum() / g.pares_esp_cli.sum()))

print("\n== 2) Mismo monto y moneda entre tipos distintos del mismo cliente (ej. Transfer->Deposit espejo) y en el mismo timestamp")
d = q("""with d as (select customer_id, currency, round(amount*100)::bigint c, count(*) k, count(distinct ttype) nt from tx group by all)
  select sum(k*(k-1)/2) pares_mismo_cliente_moneda, sum(case when nt>1 then 1 else 0 end) grupos_multitipo from d""")
print(d.to_string(index=False))
d = q("""with d as (select currency, round(amount*100)::bigint c, ts, count(*) k, count(distinct customer_id) ncli from tx group by all)
  select sum(k*(k-1)/2) pares_mismo_monto_y_ts, sum(case when ncli>1 then k*(k-1)/2 else 0 end) de_clientes_distintos from d""")
print(d.to_string(index=False))
print("\n== 3) u segun amount_usd nulo/no nulo (ARS/COP) y segun sea la primera tx del producto")
print(q("""select currency, (amount_usd is null) usd_nulo, count(*) n,
  avg((amount/(case currency when 'ARS' then 350.0 when 'COP' then 4000.0 else 1 end) - case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Payment' then 50 when 'Adjustment' then 10 when 'Deposit' then 50 else 100 end)
   / (case ttype when 'Purchase' then 495 when 'Withdrawal' then 480 when 'Payment' then 1950 when 'Adjustment' then 990 when 'Deposit' then 4950 else 9900 end)) mean_u
  from tx group by all order by 1,2""").to_string(index=False))
print(q("""with w as (select ttype, amount/(case currency when 'ARS' then 350.0 when 'COP' then 4000.0 else 1 end) a,
   row_number() over (partition by product_id order by ts, transaction_id) rn from tx)
  select ttype, (rn=1) primera_tx_producto, count(*) n,
   avg((a - case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Payment' then 50 when 'Adjustment' then 10 when 'Deposit' then 50 else 100 end)
   / (case ttype when 'Purchase' then 495 when 'Withdrawal' then 480 when 'Payment' then 1950 when 'Adjustment' then 990 when 'Deposit' then 4950 else 9900 end)) mean_u
  from w group by all order by 1,2""").to_string(index=False))

print("\n== 4) K fijo vs tasa diaria de fx: filas fuera de rango si se divide por la tasa USD->moneda del dia")
print(q("""with t as (select tx.ttype, tx.currency, tx.amount, f.rate from tx join fx f on f.date = tx.ts::date and f.src='USD' and f.dst=tx.currency
   where tx.currency in ('ARS','COP'))
  select currency, count(*) n,
   avg((amount/rate < case ttype when 'Purchase' then 5 when 'Withdrawal' then 20 when 'Payment' then 50 when 'Adjustment' then 10 when 'Deposit' then 50 else 100 end - 1e-9
     or amount/rate > case ttype when 'Purchase' then 500 when 'Withdrawal' then 500 when 'Payment' then 2000 when 'Adjustment' then 1000 when 'Deposit' then 5000 else 10000 end + 1e-9)::int)*100 pct_fuera_con_tasa_diaria
  from t group by 1 order by 1""").to_string(index=False))
