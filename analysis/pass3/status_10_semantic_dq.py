"""Inconsistencias semanticas: codigos ISO vs tipo de producto/tx, canal vs tipo, branch/lat por canal, montos por moneda."""
import duckdb, pandas as pd, numpy as np, warnings
from scipy.stats import chi2_contingency
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width',250)
def V(ct):
    chi2=chi2_contingency(ct.values, correction=False)[0]; n=ct.values.sum(); return np.sqrt(chi2/(n*(min(ct.shape)-1)))
ct = q("select ttype, channel, count(*) n from tx group by 1,2").pivot(index='ttype',columns='channel',values='n').fillna(0)
print("V ttype x channel =", round(V(ct),4)); print((ct.div(ct.sum(1),axis=0)).round(3).to_string())
ct = q("select p.ptype, t.channel, count(*) n from tx t join pr p using(product_id) group by 1,2").pivot(index='ptype',columns='channel',values='n').fillna(0)
print("V ptype x channel =", round(V(ct),4))
print(q("""select channel, count(*) n, avg(case when branch_id is null then 1 else 0 end) br_null, avg(case when lat is null then 1 else 0 end) lat_null from tx group by 1""").round(3).to_string())
print("== codigos de tarjeta (14,54) en productos sin tarjeta; 51 en depositos ==")
print(q("""select case when p.ptype like 'Tarjeta%' then 'tarjeta' else 'no_tarjeta' end tipo, t.code, count(*) n
 from tx t join pr p using(product_id) where t.status<>'Approved' and t.code is not null group by 1,2 order by 1,2""").pivot(index='tipo',columns='code',values='n').to_string())
print(q("""select count(*) n_no_aprob, sum(case when p.ptype not like 'Tarjeta%' and t.code in ('14','54') then 1 else 0 end) card_code_non_card,
  sum(case when t.ttype='Deposit' and t.code='51' then 1 else 0 end) nsf_on_deposit,
  sum(case when t.ttype='Deposit' then 1 else 0 end) deposit_no_aprob
 from tx t join pr p using(product_id) where t.status<>'Approved'""").to_string())
print("== montos por moneda y tipo ==")
print(q("""select ttype, currency, count(*) n, quantile_cont(amount,0.05) p5, median(amount) p50, quantile_cont(amount,0.95) p95, max(amount) mx from tx group by 1,2 order by 1,2""").round(1).to_string())
# pais de tx vs moneda
print(q("""select country, currency, count(*) n from tx group by 1,2""").pivot(index='country',columns='currency',values='n').to_string())
