"""Verificacion exacta de reglas deterministas: code<->status, branch/lat<->canal, merchant/mcat/tcat<->ttype, geo vs sucursal."""
import duckdb, pandas as pd, warnings
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width',250)
print(q("""select
 sum(case when code='00' and status<>'Approved' then 1 else 0 end) c00_no_aprob,
 sum(case when code in ('05','14','51','54') and status='Approved' then 1 else 0 end) crech_aprob,
 sum(case when branch_id is not null and channel not in ('ATM','Branch') then 1 else 0 end) branch_fuera,
 sum(case when lat is not null and channel not in ('ATM','Branch','POS') then 1 else 0 end) lat_fuera,
 sum(case when merchant_name is not null and ttype<>'Purchase' then 1 else 0 end) merch_fuera,
 sum(case when mcat is not null and ttype<>'Purchase' then 1 else 0 end) mcat_fuera,
 sum(case when tcat is not null and ttype not in ('Purchase','Payment') then 1 else 0 end) tcat_fuera,
 sum(case when amount_usd is not null and currency='USD' then 1 else 0 end) usd_con_amount_usd,
 count(*) n from tx""").T.to_string())
print(q("""select p.ptype, count(distinct t.ttype) n_ttypes, string_agg(distinct t.ttype, ',' order by t.ttype) ttypes from tx t join pr p using(product_id) group by 1 order by 1""").to_string())
# geo vs sucursal
print(q("""select t.channel, count(*) n, avg(case when t.city=b.city then 1 else 0 end) misma_ciudad, avg(case when t.country=b.country then 1 else 0 end) mismo_pais,
  median(sqrt(power(t.lat-b.lat,2)+power(t.lon-b.lon,2))) med_dist_grados
 from tx t join br b using(branch_id) where t.branch_id is not null group by 1""").to_string())
# lat/lon vs pais
print(q("""select country, count(*) n, min(lat), max(lat), min(lon), max(lon) from tx where lat is not null group by 1""").round(2).to_string())
