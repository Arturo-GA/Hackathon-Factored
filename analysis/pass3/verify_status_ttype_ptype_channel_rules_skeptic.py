"""Verificador escéptico: reglas estructurales tx (ptype->ttype, code<->status, merchant->mcat->tcat, branch/lat<->canal, canal aleatorio)."""
import duckdb, pandas as pd, numpy as np, warnings
from scipy.stats import chi2_contingency
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 50)
def V(ct):
    ct = ct.values.astype(float); chi2 = chi2_contingency(ct, correction=False)[0]
    n = ct.sum(); r, k = ct.shape; return np.sqrt(chi2/(n*(min(r,k)-1)))

print(q("select count(*) n, count(product_id) np, count(distinct product_id) ndp from tx").to_string())
print("pr ptypes:\n", q("select ptype, count(*) n, sum(case when pstatus='Active' then 1 else 0 end) act from pr group by 1 order by 1").to_string())
a = q("select p.ptype, t.ttype, count(*) n from tx t join pr p using(product_id) group by 1,2")
print(a.pivot(index='ptype', columns='ttype', values='n').fillna(0).astype(int).to_string())
print("anti-join tx->pr:", q("select count(*) from tx anti join pr using(product_id)").iloc[0,0])
# baseline de restricción: ¿cuántas celdas ptype×ttype vacías? ¿es solo por diseño semántico?
# (b)
b = q("select status, coalesce(code,'NULL') code, count(*) n from tx group by 1,2").pivot(index='status', columns='code', values='n').fillna(0).astype(int)
print("\nstatus x code\n", b.to_string())
# (c)
print(q("select ttype, count(*) n, count(merchant_name) m, count(mcat) mc, count(tcat) tc from tx group by 1 order by 1").to_string())
print(q("select merchant_name, count(distinct mcat) k, any_value(mcat) mc, count(*) n from tx where merchant_name is not null group by 1 order by 3").to_string())
print(q("""select count(*) purch, sum(case when merchant_name is null then 1 else 0 end) sin_merch,
 sum(case when mcat is null then 1 else 0 end) sin_mcat, sum(case when tcat is null then 1 else 0 end) sin_tcat,
 sum(case when tcat is not null and mcat is not null and tcat=mcat then 1 else 0 end) tcat_eq,
 sum(case when tcat is not null and mcat is not null then 1 else 0 end) ambos,
 sum(case when merchant_name is not null and mcat is null then 1 else 0 end) merch_sin_mcat
 from tx where ttype='Purchase'""").T.to_string())
# ¿tcat en Purchase sin mcat es deducible del merchant?
print("merchant->tcat cuando mcat nulo:", q("""select count(*) n, sum(case when t.tcat=m.mc then 1 else 0 end) ok from tx t join
 (select merchant_name, any_value(mcat) mc from tx where mcat is not null group by 1) m using(merchant_name)
 where t.ttype='Purchase' and t.mcat is null and t.tcat is not null""").to_string())
# (d)
print(q("""select channel, count(*) n, avg((branch_id is not null)::int) pb, avg((lat is not null)::int) plat,
 sum(case when (lat is null)<>(lon is null) then 1 else 0 end) desp from tx group by 1 order by 1""").round(4).to_string())
print("branch_id no existe en br:", q("select count(*) from tx t where branch_id is not null and branch_id not in (select branch_id from br)").iloc[0,0])
print(q("""select avg(case when t.country=b.country then 1 else 0 end) mismo_pais, avg(case when t.city=b.city then 1 else 0 end) misma_ciudad, count(*) n
 from tx t join br b using(branch_id)""").to_string())
# lat en ATM/Branch: ¿coincide con coords de sucursal?
print(q("""select t.channel, count(*) n, median(abs(t.lat-b.lat)+abs(t.lon-b.lon)) med_l1 from tx t join br b using(branch_id) where t.lat is not null group by 1""").to_string())
# canal independiente: ttype, ptype, status, country, fraud, code, currency
for col, j in [("ttype",""),("status",""),("country",""),("currency",""),("coalesce(code,'NULL')",""),("fraud::varchar","")]:
    ct = q(f"select {col} k, channel, count(*) n from tx group by 1,2").pivot(index='k', columns='channel', values='n').fillna(0)
    print(f"V(channel,{col})={V(ct):.4f}")
ctp = q("select p.ptype k, t.channel, count(*) n from tx t join pr p using(product_id) group by 1,2").pivot(index='k', columns='channel', values='n').fillna(0)
print(f"V(channel,ptype)={V(ctp):.4f}")
ch = q("select ttype, channel, count(*) n from tx group by 1,2").pivot(index='ttype', columns='channel', values='n').fillna(0)
print((ch.div(ch.sum(1),axis=0)*100).round(1).to_string())
# canal vs monto
print(q("select channel, avg(amount) m, median(amount) med from tx group by 1 order by 1").round(1).to_string())
# canal a nivel cliente: ¿clientes con canal preferido? share del canal modal vs esperado
print(q("""with c as (select customer_id, channel, count(*) n from tx group by 1,2), t as (select customer_id, sum(n) tot, max(n) mx from c group by 1)
 select avg(mx::double/tot) share_modal, median(tot) med_tx from t where tot>=20""").to_string())
# status por ttype
st = q("select ttype, status, count(*) n from tx group by 1,2").pivot(index='ttype', columns='status', values='n').fillna(0)
print((st.div(st.sum(1),axis=0)*100).round(2).to_string())
# Adjustment: signo de monto / tcat
print(q("select ttype, min(amount) mn, max(amount) mx, avg((amount<0)::int) pneg, count(tcat) tc from tx group by 1 order by 1").to_string())
print("\n--- extras ---")
print(q("""select channel, sum(case when lat is not null and lon is null then 1 else 0 end) lat_sin_lon,
 sum(case when lat is null and lon is not null then 1 else 0 end) lon_sin_lat, sum(case when lat is not null and lon is not null then 1 else 0 end) ambos
 from tx where channel in ('ATM','Branch','POS') group by 1""").to_string())
print(q("select tcat, count(*) n from tx where ttype='Payment' group by 1 order by 2 desc").to_string())
# mezcla ttype dentro de ptype (proporciones)
a = q("select p.ptype, t.ttype, count(*) n from tx t join pr p using(product_id) group by 1,2").pivot(index='ptype', columns='ttype', values='n').fillna(0)
print((a.div(a.sum(1),axis=0)*100).round(1).to_string())
