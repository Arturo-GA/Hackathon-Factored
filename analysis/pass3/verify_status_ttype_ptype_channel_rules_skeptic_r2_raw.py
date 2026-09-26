"""Escéptico r2 (parte 2): ¿las reglas existen en el CSV crudo o son artefacto del pipeline (bronze/TRY_CAST)?
Además: calidad de lat/lon (valores no numéricos, (0,0) por país) y V(ptype,ttype) ya conocido."""
import duckdb, pandas as pd, numpy as np, warnings
from scipy.stats import chi2_contingency
warnings.filterwarnings('ignore')
con = duckdb.connect(':memory:')
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60)
RAW = "read_csv('data/raw/transactions/*/*/*/*.csv', all_varchar=true, header=true, union_by_name=true)"
PR = "read_csv('data/raw/products.csv', all_varchar=true, header=true)"
e = lambda c: f"(coalesce(trim({c}),'')='')"   # vacío en crudo

print(q(f"""select count(*) n,
  sum(case when not {e('merchant_name')} and transaction_type<>'Purchase' then 1 else 0 end) merch_fuera,
  sum(case when not {e('merchant_category')} and transaction_type<>'Purchase' then 1 else 0 end) mcat_fuera,
  sum(case when not {e('transaction_category')} and transaction_type not in ('Purchase','Payment') then 1 else 0 end) tcat_fuera,
  sum(case when not {e('transaction_category')} and not {e('merchant_category')} and transaction_category<>merchant_category then 1 else 0 end) tcat_ne_mcat,
  sum(case when response_code='00' and transaction_status<>'Approved' then 1 else 0 end) c00_no_aprob,
  sum(case when response_code in ('05','14','51','54') and transaction_status='Approved' then 1 else 0 end) rech_aprob,
  sum(case when {e('response_code')} then 1 else 0 end) code_vacio,
  sum(case when not {e('branch_id')} and channel not in ('ATM','Branch') then 1 else 0 end) branch_fuera,
  sum(case when not {e('latitude')} and channel not in ('ATM','Branch','POS') then 1 else 0 end) lat_fuera,
  sum(case when not {e('longitude')} and channel not in ('ATM','Branch','POS') then 1 else 0 end) lon_fuera,
  sum(case when not {e('latitude')} and try_cast(latitude as double) is null then 1 else 0 end) lat_no_num,
  sum(case when not {e('longitude')} and try_cast(longitude as double) is null then 1 else 0 end) lon_no_num,
  sum(case when {e('latitude')} <> {e('longitude')} then 1 else 0 end) latlon_desync,
  count(distinct merchant_name) n_merch
  from {RAW}""").T.to_string())

print("\n(a) en crudo, ptype x ttype:")
a = q(f"""select p.product_type ptype, t.transaction_type ttype, count(*) n from {RAW} t left join {PR} p using(product_id) group by 1,2""")
a = a.pivot(index='ptype', columns='ttype', values='n').fillna(0).astype(int)
print(a.to_string())
ct = a.values.astype(float); chi2 = chi2_contingency(ct, correction=False)[0]
print("V(ptype,ttype) crudo =", round(np.sqrt(chi2 / (ct.sum() * (min(ct.shape) - 1))), 4), "(YA SABEMOS: 0.48)")

print("\nlat/lon: fracción cerca de (0,0) y cerca del centro de su país, por país de tx (solo coords completas)")
print(q(f"""with g as (select transaction_country c, try_cast(latitude as double) la, try_cast(longitude as double) lo from {RAW}
   where not {e('latitude')} and not {e('longitude')})
  select c, count(*) n, round(avg((abs(la)<=1.5 and abs(lo)<=1.5)::int),3) p_cerca_00,
   round(avg((la between 14 and 33 and lo between -118 and -86)::int),3) p_en_mexico,
   round(avg((la between -4.5 and 13 and lo between -79.5 and -66)::int),3) p_en_colombia,
   round(avg((la between -55.5 and -21 and lo between -74 and -53)::int),3) p_en_argentina
  from g group by 1 order by 2 desc""").to_string())
