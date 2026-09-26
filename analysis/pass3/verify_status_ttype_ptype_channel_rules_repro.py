"""Verificacion independiente: reglas estructurales tx (ptype->ttype, code<->status, merchant->mcat->tcat, branch/lat<->canal, canal aleatorio)."""
import duckdb, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 50)

print("N tx:", q("select count(*) n, count(product_id) np from tx").to_string())
# (a) ptype x ttype
a = q("""select p.ptype, t.ttype, count(*) n from tx t left join pr p using(product_id) group by 1,2""")
print("\n(a) ptype x ttype\n", a.pivot(index='ptype', columns='ttype', values='n').fillna(0).astype(int).to_string())
print("tx sin match en pr:", q("select count(*) from tx t anti join pr p using(product_id)").iloc[0,0])

# (b) code x status
b = q("select status, coalesce(code,'NULL') code, count(*) n from tx group by 1,2")
print("\n(b) status x code\n", b.pivot(index='status', columns='code', values='n').fillna(0).astype(int).to_string())

# (c) merchant/mcat/tcat
c = q("""select ttype, count(*) n, count(merchant_name) merch, count(mcat) mcat, count(tcat) tcat from tx group by 1 order by 1""")
print("\n(c) no-nulos por ttype\n", c.to_string())
print(q("""select count(distinct merchant_name) n_merch, max(k) max_mcat_por_merch from (select merchant_name, count(distinct mcat) k from tx where merchant_name is not null group by 1)""").to_string())
print(q("""select count(*) ambos, sum(case when tcat=mcat then 1 else 0 end) iguales,
  sum(case when merchant_name is not null and mcat is null then 1 else 0 end) merch_sin_mcat,
  sum(case when merchant_name is null and mcat is not null then 1 else 0 end) mcat_sin_merch
  from tx where ttype='Purchase' and tcat is not null and mcat is not null""").to_string())
print(q("""select sum(case when merchant_name is not null then 1 else 0 end) merch_nn, sum(case when mcat is not null then 1 else 0 end) mcat_nn,
  sum(case when merchant_name is not null and mcat is null then 1 else 0 end) merch_sin_mcat,
  sum(case when merchant_name is null and mcat is not null then 1 else 0 end) mcat_sin_merch,
  sum(case when tcat is not null then 1 else 0 end) tcat_nn, count(*) n from tx where ttype='Purchase'""").to_string())
print("tcat valores por ttype:\n", q("select ttype, count(distinct tcat) k, string_agg(distinct tcat, '|') v from tx group by 1 order by 1").to_string())

# (d) branch / lat por canal
d = q("""select channel, count(*) n, avg((branch_id is not null)::int) p_branch, avg((lat is not null)::int) p_lat, avg((lon is not null)::int) p_lon,
   sum(case when (lat is null) <> (lon is null) then 1 else 0 end) lat_lon_desp from tx group by 1 order by 1""")
print("\n(d) llenado por canal\n", d.round(4).to_string())

# Adjustment
print("\nAdjustment por ptype:\n", q("select p.ptype, count(*) n from tx t join pr p using(product_id) where ttype='Adjustment' group by 1 order by 2 desc").to_string())
st = q("select ttype, status, count(*) n from tx group by 1,2")
stp = st.pivot(index='ttype', columns='status', values='n').fillna(0)
print("status % por ttype\n", (stp.div(stp.sum(1), axis=0)*100).round(2).to_string())

# canal vs ttype / ptype
def cramer(ct):
    from scipy.stats import chi2_contingency
    ct = ct.values.astype(float)
    chi2 = chi2_contingency(ct, correction=False)[0]
    n = ct.sum(); r, k = ct.shape
    return np.sqrt(chi2 / (n * (min(r, k) - 1)))
ch = q("select ttype, channel, count(*) n from tx group by 1,2").pivot(index='ttype', columns='channel', values='n').fillna(0)
print("\ncanal % por ttype\n", (ch.div(ch.sum(1), axis=0)*100).round(2).to_string())
print("V(ttype,channel)=", round(cramer(ch), 5))
chp = q("select p.ptype, t.channel, count(*) n from tx t join pr p using(product_id) group by 1,2").pivot(index='ptype', columns='channel', values='n').fillna(0)
print("V(ptype,channel)=", round(cramer(chp), 5))
print("canal global %:", (ch.sum(0)/ch.values.sum()*100).round(2).to_dict())

# Extra: merchant -> tcat directo (incluye compras con mcat nulo); tcat en Payment; nulos de code por status
print("\nmerchant->tcat en Purchase:", q("""select count(*) n, sum(case when t.tcat=m.mc then 1 else 0 end) ok from tx t
  join (select merchant_name, any_value(mcat) mc from tx where mcat is not null group by 1) m using(merchant_name)
  where t.ttype='Purchase' and t.tcat is not null""").to_string())
pc = q("select p.ptype, t.tcat, count(*) n from tx t join pr p using(product_id) where t.ttype='Payment' and t.tcat is not null group by 1,2").pivot(index='ptype', columns='tcat', values='n').fillna(0)
print("tcat en Payment por ptype (%)\n", (pc.div(pc.sum(1), axis=0)*100).round(1).to_string())
print("V(ptype,tcat | Payment)=", round(cramer(pc), 4))
print("code nulo % por status:\n", q("select status, avg((code is null)::int)*100 pnull from tx group by 1").round(2).to_string())
