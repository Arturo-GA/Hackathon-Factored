# Complemento: (1) tcat en Payment tiene semantica?  (2) el comercio nulo se puede recuperar con otra columna?
# (3) la categoria se relaciona con monto/estado/fraude (utilidad mas alla de describir)?
import duckdb, numpy as np, pandas as pd
from scipy.stats import chi2_contingency

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
df = lambda s: con.execute(s).df()

def v_of(sql, r, c):
    d = df(sql)
    ct = d.pivot(index=r, columns=c, values='n').fillna(0).values
    chi2 = chi2_contingency(ct)[0]; n = ct.sum()
    return float(np.sqrt(chi2 / (n * (min(ct.shape) - 1)))), int(n), ct.shape

# (1) tcat en Payment vs tipo de producto / canal
print('V tcat x ptype (Payment)        = %.4f n=%d dims=%s' % v_of("""select p.ptype, t.tcat, count(*) n from tx t join pr p using(product_id)
    where t.ttype='Payment' and t.tcat is not null group by 1,2""", 'ptype', 'tcat'))
print('V tcat x channel (Payment)      = %.4f n=%d dims=%s' % v_of("""select channel, tcat, count(*) n from tx
    where ttype='Payment' and tcat is not null and channel is not null group by 1,2""", 'channel', 'tcat'))
# (2) comercio vs pais / canal / ciudad dentro de su categoria (se puede imputar el comercio?)
print('V merchant x country (Purchase) = %.4f n=%d dims=%s' % v_of("""select merchant_name, country, count(*) n from tx
    where ttype='Purchase' and merchant_name is not null and country is not null group by 1,2""", 'merchant_name', 'country'))
print('V merchant x channel (Purchase) = %.4f n=%d dims=%s' % v_of("""select merchant_name, channel, count(*) n from tx
    where ttype='Purchase' and merchant_name is not null and channel is not null group by 1,2""", 'merchant_name', 'channel'))
print(df("""select count(distinct city) ciudades_por_comercio_min from (select merchant_name, city from tx
    where ttype='Purchase' and merchant_name is not null group by 1,2) group by merchant_name order by 1 limit 1""").to_string(), '\n')
# Mismo cliente repite comercio? (si un cliente siempre usa el mismo comercio se podria imputar por cliente)
print(df("""with c as (select customer_id, merchant_name, count(*) n from tx where ttype='Purchase' and merchant_name is not null group by 1,2),
    s as (select customer_id, sum(n) tot, max(n) mx from c group by 1 having sum(n) >= 10)
    select count(*) clientes_10mas_compras, avg(mx/tot) share_comercio_top_prom from s""").to_string(), '\n')

# (3) categoria vs monto / estado / fraude en compras
print(df("""with m as (select merchant_name, mode(mcat) mc from tx where merchant_name is not null and mcat is not null group by 1)
    select coalesce(t.mcat, m.mc, t.tcat) cat, count(*) n,
      round(median(t.amount_usd), 2) mediana_usd, round(avg(t.amount_usd), 2) media_usd,
      round(100*avg((t.status='Declined')::int), 3) pct_declined, round(100*avg(t.fraud::int), 3) pct_fraude
    from tx t left join m using(merchant_name) where t.ttype='Purchase' group by 1 order by n desc""").to_string(), '\n')
