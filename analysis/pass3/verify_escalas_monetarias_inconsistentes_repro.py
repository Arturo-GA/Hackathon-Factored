import duckdb, numpy as np, pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(s, title=None):
    if title: print('==', title)
    print(con.execute(s).df().to_string(), '\n')

# 1. Ingreso crudo por pais x segmento
q("""select country, segment, count(*) n, min(income) mn, median(income) med, max(income) mx
     from cu group by all order by segment, country""", "ingreso crudo")
# estimar K empiricamente: min/max/median por segmento relativo a Colombia/Argentina/Mexico (sin suponer)
q("""with s as (select country, segment, min(income) mn, median(income) med, max(income) mx from cu group by all)
select a.segment, a.country,
  a.mn/b.mn r_min_vs_MX, a.med/b.med r_med_vs_MX, a.mx/b.mx r_max_vs_MX
from s a join s b on a.segment=b.segment and b.country='México' order by 1,2""", "ratios vs Mexico")
q("select distinct country from cu")

# 2. Normalizado con K
K="(case country when 'Argentina' then 350 when 'Colombia' then 4000 else 17 end)"
q(f"""select segment, country, round(min(income/{K}),1) mn, round(median(income/{K}),1) med, round(max(income/{K}),1) mx
      from cu group by all order by 1,2""", "ingreso normalizado")
# FX real
q("""select src, dst, count(*) n, min(rate) mn, median(rate) med, max(rate) mx from fx where src='USD' group by all order by 2""", "fx USD->x")
# 3. moneda de productos y tx por pais del cliente
q("""select cu.country, p.currency, count(*) n from pr p join cu using(customer_id) group by all order by 1,2""", "moneda productos por pais cliente")
q("""select currency, count(*) n from pr group by 1""", "monedas pr")
q("""select cu.country, t.currency, count(*) n from tx t join cu using(customer_id) group by all order by 1,2""", "moneda tx por pais cliente")
# 4. gasto mensual / ingreso
q(f"""with t as (select customer_id, sum(amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end))/36.0 m_usd,
                  sum(amount)/36.0 m_raw
            from tx where ttype in ('Purchase','Withdrawal') group by 1)
select cu.country, count(*) n, median(t.m_usd) med_m_usd, median(t.m_raw) med_m_raw, median(cu.income) med_inc,
   median(t.m_raw/cu.income) ratio_raw_local, median(t.m_usd/cu.income) ratio_usd_vs_rawinc, median(t.m_usd/(cu.income/{K})) ratio_norm
from t join cu using(customer_id) group by 1""", "gasto/ingreso")
