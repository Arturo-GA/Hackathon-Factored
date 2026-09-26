# Verificador escéptico (r3): regla amount_usd = round(amount/K,2), K fijo; nulos; fx
import duckdb, time
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
import pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
def q(s, show=True):
    df = con.execute(s).df()
    if show: print(df.to_string(), '\n', flush=True)
    return df

print("== 0. esquema relevante ==")
q("select column_name, data_type from information_schema.columns where table_name='tx' and column_name in ('amount','amount_usd','currency','ts','process_date')")
q("select column_name, data_type from information_schema.columns where table_name='fx'")

print("== 1. nulos y rango por moneda ==")
q("""select currency, count(*) n, count(amount_usd) nn, round(1-count(amount_usd)/count(*)::double,5) null_rate,
     min(amount) amin, max(amount) amax, sum((amount<=0)::int) nonpos,
     sum((amount_usd is not null and amount_usd=0)::int) usd_zero,
     sum((amount_usd is not null and abs(amount_usd-amount)<0.005)::int) usd_eq_amount
     from tx group by 1 order by 1""")
q("select count(*) n, 1-count(amount_usd)/count(*)::double null_rate from tx")

print("== 2. barrido de K: fraccion de igualdad exacta amount_usd = round(amount/K,2) ==")
q("""with t as (select currency, amount, amount_usd from tx where amount_usd is not null and currency in ('ARS','COP')),
k as (select * from (values ('ARS',349.0),('ARS',349.9),('ARS',349.99),('ARS',350.0),('ARS',350.01),('ARS',350.1),('ARS',351.0),
   ('COP',3990.0),('COP',3999.0),('COP',3999.9),('COP',4000.0),('COP',4000.1),('COP',4001.0),('COP',4010.0)) v(currency,K))
select t.currency, k.K, count(*) n, round(avg((amount_usd = round(amount/K,2))::int),6) exact
from t join k using(currency) group by all order by 1,2""")
print(f"[t={time.time()-t0:.0f}s]")

print("== 3. filas que NO cumplen: son empates de medio centavo? ==")
# A = amount en centavos (entero); empate exacto si A*1 / K*... frac(A/K) = 0.5  <=> mod(2A, 2K)==K (K entero)
q("""with t as (select currency, amount, amount_usd, round(amount*100)::BIGINT A,
       case currency when 'ARS' then 350 else 4000 end K from tx where amount_usd is not null and currency in ('ARS','COP'))
select currency, count(*) n,
  sum((amount_usd <> round(amount/K,2))::int) n_mismatch,
  round(avg((amount_usd <> round(amount/K,2))::int),6) mismatch_rate,
  sum((abs(amount*100 - A) > 1e-6)::int) amount_not_2dec,
  sum(((2*A) % (2*K) = K)::int) n_tie,
  round(avg(((2*A) % (2*K) = K)::int),6) tie_rate,
  sum(((2*A) % (2*K) = K and amount_usd <> round(amount/K,2))::int) mismatch_and_tie,
  sum(((2*A) % (2*K) <> K and amount_usd <> round(amount/K,2))::int) mismatch_not_tie,
  sum(((2*A) % (2*K) = K and amount_usd = floor(amount*100/K)/100)::int) tie_rounded_down,
  sum(((2*A) % (2*K) = K and amount_usd = ceil(amount*100/K)/100)::int) tie_rounded_up,
  max(abs(amount_usd - amount/K)) maxdiff
from t group by 1 order by 1""")
# en empates: redondeo a par (banquero)?
q("""with t as (select currency, amount, amount_usd, round(amount*100)::BIGINT A,
       case currency when 'ARS' then 350 else 4000 end K from tx where amount_usd is not null and currency in ('ARS','COP')),
e as (select *, floor(A/K)::BIGINT lo from t where (2*A) % (2*K) = K)
select currency, count(*) n_tie,
  round(avg((round(amount_usd*100)::BIGINT = case when lo % 2 = 0 then lo else lo+1 end)::int),4) half_even_match,
  round(avg((round(amount_usd*100)::BIGINT = lo+1)::int),4) half_up_match
from e group by 1 order by 1""")
print(f"[t={time.time()-t0:.0f}s]")

print("== 4. K por mes: desviacion relativa maxima del cociente con amount_usd>=50 (fx diario daria ~1e-2) ==")
d = q("""select currency, date_trunc('month', ts) m, count(*) n, median(amount/amount_usd) med_ratio,
       max(abs(amount/amount_usd/(case currency when 'ARS' then 350 else 4000 end)-1)) max_reldev
       from tx where amount_usd >= 50 and currency in ('ARS','COP') group by all order by 1,2""", show=False)
print(d.groupby('currency').agg(meses=('m','count'), n=('n','sum'), med_min=('med_ratio','min'), med_max=('med_ratio','max'),
      max_reldev=('max_reldev','max')).to_string(), '\n')
print(f"[t={time.time()-t0:.0f}s]")
