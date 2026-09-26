"""Verificador escéptico (ronda 2) de status_ttype_ptype_channel_rules.

Intenta explicar/romper las reglas: integridad del join, vacíos '' vs NULL, bicondicional code<->status,
tautología tcat=mcat, independencia de nulos (inyección 5%), sentido de lat/lon y branch, canal aleatorio,
y utilidad real (¿'compra en cuenta de ahorro' es imposible o hay que redirigir a la tarjeta de débito?).
Solo agregaciones en SQL.
"""
import duckdb, pandas as pd, numpy as np, warnings
from scipy.stats import chi2_contingency
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60)


def V(ct):
    a = ct.values.astype(float)
    a = a[a.sum(1) > 0][:, a.sum(0) > 0]
    chi2 = chi2_contingency(a, correction=False)[0]
    n = a.sum(); r, k = a.shape
    return np.sqrt(chi2 / (n * (min(r, k) - 1)))


print("=== 0. Integridad ===")
print(q("""select count(*) n, count(distinct transaction_id) n_id, count(product_id) n_pid,
  sum(case when ttype='' then 1 else 0 end) e_ttype, sum(case when tcat='' then 1 else 0 end) e_tcat,
  sum(case when merchant_name='' then 1 else 0 end) e_merch, sum(case when mcat='' then 1 else 0 end) e_mcat,
  sum(case when branch_id='' then 1 else 0 end) e_branch, sum(case when code='' then 1 else 0 end) e_code,
  sum(case when channel is null or channel='' then 1 else 0 end) e_chan, sum(case when status is null or status='' then 1 else 0 end) e_status,
  sum(case when ttype is null then 1 else 0 end) null_ttype from tx""").T.to_string())
print(q("select count(*) n, count(distinct product_id) nd from pr").to_string())
print("tx sin producto en pr:", q("select count(*) from tx anti join pr using(product_id)").iloc[0, 0])
print(q("""select avg((t.customer_id=p.customer_id)::int) same_cust, count(*) n from tx t join pr p using(product_id)""").to_string())
print("valores distintos: ptype", q("select list(distinct ptype order by ptype) from pr").iloc[0, 0])
print("ttype", q("select list(distinct ttype order by ttype) from tx").iloc[0, 0], " status", q("select list(distinct status order by status) from tx").iloc[0, 0],
      " code", q("select list(distinct code order by code) from tx").iloc[0, 0], " channel", q("select list(distinct channel order by channel) from tx").iloc[0, 0])

print("\n=== A. ptype x ttype (ceros estructurales) ===")
a = q("select p.ptype, t.ttype, count(*) n from tx t join pr p using(product_id) group by 1,2").pivot(index='ptype', columns='ttype', values='n').fillna(0).astype(int)
print(a.to_string())
print("% por fila:\n", (a.div(a.sum(1), axis=0) * 100).round(2).to_string())
fam = """case when p.ptype like 'Cuenta%' then 'cuenta' when p.ptype like 'Tarjeta%' then 'tarjeta' else 'otro' end"""
print(q(f"""select sum(case when {fam}='cuenta' and t.ttype not in ('Deposit','Payment','Transfer','Withdrawal') then 1
              when {fam}='tarjeta' and t.ttype not in ('Purchase','Payment','Withdrawal') then 1
              when {fam}='otro' and t.ttype not in ('Adjustment','Payment','Transfer') then 1 else 0 end) viol_a, count(*) n
  from tx t join pr p using(product_id)""").to_string())
# ¿productos con tx de un solo 'grupo'? n de ptypes por ttype
print("ttype -> ptypes con soporte:", q("select t.ttype, count(distinct p.ptype) k from tx t join pr p using(product_id) group by 1 order by 1").to_dict('records'))

print("\n=== B. status x code ===")
b = q("select status, coalesce(code,'NULL') code, count(*) n from tx group by 1,2").pivot(index='status', columns='code', values='n').fillna(0).astype(int)
print(b.to_string())
print(q("""select avg(case when status='Approved' then 1 else 0 end) filter (where code='00') p_aprob_dado_00,
  avg(case when code='00' then 1 else 0 end) filter (where status='Approved') p_00_dado_aprob,
  avg(case when code='00' then 1 else 0 end) filter (where status='Approved' and code is not null) p_00_dado_aprob_nonull,
  avg(case when status<>'Approved' then 1 else 0 end) filter (where code in ('05','14','51','54')) p_noaprob_dado_rech,
  avg(case when code is null then 1 else 0 end) filter (where status<>'Approved') p_null_noaprob,
  avg(case when code is null then 1 else 0 end) filter (where status='Approved') p_null_aprob from tx""").T.round(5).to_string())
cb = q("select status, code, count(*) n from tx where status<>'Approved' and code is not null group by 1,2").pivot(index='status', columns='code', values='n').fillna(0)
print("mezcla de codigos por status no aprobado (%):\n", (cb.div(cb.sum(1), axis=0) * 100).round(2).to_string(), "\nV(status,code | no aprob)=", round(V(cb), 4))
print("code nulo por ttype (%):", q("select ttype, round(avg((code is null)::int)*100,2) p from tx group by 1 order by 1").set_index('ttype')['p'].to_dict())

print("\n=== C. merchant / mcat / tcat ===")
print(q("""select ttype, count(*) n, count(merchant_name) merch, count(mcat) mcat, count(tcat) tcat,
  round(100.0*count(tcat)/count(*),2) pct_tcat from tx group by 1 order by 1""").to_string())
print(q("""select count(distinct merchant_name) n_merch, count(distinct mcat) n_mcat, max(k) max_mcat_por_merch from
  (select merchant_name, mcat, count(distinct mcat) over (partition by merchant_name) k from
    (select distinct merchant_name, mcat from tx where merchant_name is not null and mcat is not null))""").to_string())
print("comercios por mcat:", q("""select mcat, count(distinct merchant_name) k from tx where mcat is not null and merchant_name is not null group by 1 order by 1""").set_index('mcat')['k'].to_dict())
# Independencia de nulos dentro de Purchase (¿inyección aleatoria 5% por columna?)
pn = q("""select (merchant_name is null) m_null, (mcat is null) c_null, (tcat is null) t_null, count(*) n from tx where ttype='Purchase' group by 1,2,3 order by 1,2,3""")
print(pn.to_string())
N = pn.n.sum()
for c1, c2 in [('m_null', 'c_null'), ('c_null', 't_null'), ('m_null', 't_null')]:
    p1 = pn.loc[pn[c1], 'n'].sum() / N; p2 = pn.loc[pn[c2], 'n'].sum() / N; p12 = pn.loc[pn[c1] & pn[c2], 'n'].sum() / N
    print(f"  P({c1})={p1:.4f} P({c2})={p2:.4f} P(ambos)={p12:.5f} esperado indep={p1*p2:.5f} ratio={p12/(p1*p2):.3f}")
print(q("""select count(*) ambos, sum((tcat=mcat)::int) iguales from tx where ttype='Purchase' and tcat is not null and mcat is not null""").to_string())
# ¿tcat en Purchase se deduce del comercio cuando mcat es nulo? y ¿mcat nulo pero tcat presente?
print(q("""with m as (select merchant_name, any_value(mcat) mc from tx where mcat is not null and merchant_name is not null group by 1)
  select count(*) n, sum((t.tcat=m.mc)::int) ok from tx t join m using(merchant_name) where t.ttype='Purchase' and t.tcat is not null""").to_string())
# tcat en Payment: ¿mezcla igual a la de Purchase? ¿depende del ptype?
tp = q("""select t.ttype, t.tcat, count(*) n from tx t where t.tcat is not null group by 1,2""").pivot(index='tcat', columns='ttype', values='n').fillna(0)
print("mezcla tcat (%) por ttype:\n", (tp.div(tp.sum(0), axis=1) * 100).round(2).to_string())
pc = q("select p.ptype, t.tcat, count(*) n from tx t join pr p using(product_id) where t.ttype='Payment' and t.tcat is not null group by 1,2").pivot(index='ptype', columns='tcat', values='n').fillna(0)
print("V(ptype,tcat | Payment)=", round(V(pc), 4), " % Payment en Seguro/Préstamo con tcat=Entertainment:",
      round(100 * pc.loc[[i for i in pc.index if i.startswith('Seguro') or i.startswith('Pr')], 'Entertainment'].sum() / pc.loc[[i for i in pc.index if i.startswith('Seguro') or i.startswith('Pr')]].values.sum(), 2) if 'Entertainment' in pc.columns else 'NA')

print("\n=== D. branch / lat / lon por canal ===")
d = q("""select channel, count(*) n, round(avg((branch_id is not null)::int),4) p_branch, round(avg((lat is not null)::int),4) p_lat,
  round(avg((lon is not null)::int),4) p_lon, round(avg((lat is not null and lon is not null)::int),4) p_ambos,
  sum(((lat is null)<>(lon is null))::int) desync from tx group by 1 order by 1""")
print(d.to_string())
fis = d[d.channel.isin(['ATM', 'Branch', 'POS'])]
pl = (fis.p_lat * fis.n).sum() / fis.n.sum(); plo = (fis.p_lon * fis.n).sum() / fis.n.sum(); pb = (fis.p_ambos * fis.n).sum() / fis.n.sum()
print(f"  fisicos: P(lat)={pl:.4f} P(lon)={plo:.4f} P(ambos)={pb:.4f}  -> P(ambos)/P(lat) = {pb/pl:.4f} (0.95 si lon se anula al 5% indep.)  P(lat)/0.95={pl/0.95:.4f}")
print(q("""select sum((b.branch_id is null)::int) branch_inexistente, count(*) n from tx t left join br b using(branch_id) where t.branch_id is not null""").to_string())
print(q("""select round(avg((t.country=b.country)::int),4) tx_pais_eq_suc, round(avg((t.city=b.city)::int),4) tx_ciudad_eq_suc,
  round(avg((c.country=b.country)::int),4) cli_pais_eq_suc, round(avg((t.country=c.country)::int),4) tx_pais_eq_cli, count(*) n
  from tx t join br b using(branch_id) join cu c on c.customer_id=t.customer_id""").to_string())
print("rango lat/lon por pais tx:\n", q("""select country, count(*) n, round(min(lat),2) lat_min, round(quantile_cont(lat,0.5),2) lat_med, round(max(lat),2) lat_max,
  round(min(lon),2) lon_min, round(quantile_cont(lon,0.5),2) lon_med, round(max(lon),2) lon_max from tx where lat is not null and lon is not null group by 1 order by 1""").to_string())
print("rango lat/lon de sucursales:\n", q("select country, round(min(lat),2) a, round(max(lat),2) b, round(min(lon),2) c, round(max(lon),2) d from br group by 1").to_string())

print("\n=== E. canal vs ttype / ptype / otros ===")
ch = q("select ttype, channel, count(*) n from tx group by 1,2").pivot(index='ttype', columns='channel', values='n').fillna(0)
print((ch.div(ch.sum(1), axis=0) * 100).round(2).to_string())
print("V(ttype,canal)=", round(V(ch), 5))
chp = q("select p.ptype, t.channel, count(*) n from tx t join pr p using(product_id) group by 1,2").pivot(index='ptype', columns='channel', values='n').fillna(0)
print("V(ptype,canal)=", round(V(chp), 5))
for col in ["status", "country", "currency", "coalesce(mcat,'NA')", "fraud::varchar", "coalesce(code,'NA')", "year(ts)::varchar"]:
    ct = q(f"select {col} k, channel, count(*) n from tx group by 1,2").pivot(index='k', columns='channel', values='n').fillna(0)
    print(f"  V(canal,{col})={V(ct):.4f}")
cm = q("""select merchant_name k, channel, count(*) n from tx where merchant_name is not null group by 1,2""").pivot(index='k', columns='channel', values='n').fillna(0)
print(f"  V(canal,merchant)={V(cm):.4f}")
# canal vs pstatus/opening_channel/app del producto
for col in ["p.opening_channel", "p.app::varchar", "p.currency"]:
    ct = q(f"select {col} k, t.channel, count(*) n from tx t join pr p using(product_id) group by 1,2").pivot(index='k', columns='channel', values='n').fillna(0)
    print(f"  V(canal,{col})={V(ct):.4f}")

print("\n=== F. Adjustment ===")
print(q("select p.ptype, count(*) n from tx t join pr p using(product_id) where t.ttype='Adjustment' group by 1 order by 2 desc").to_string())
st = q("select ttype, status, count(*) n from tx group by 1,2").pivot(index='ttype', columns='status', values='n').fillna(0)
print((st.div(st.sum(1), axis=0) * 100).round(2).to_string(), "\nV(ttype,status)=", round(V(st), 5))
print(q("""select ttype, round(avg((amount<0)::int),4) p_neg, round(quantile_cont(amount_usd,0.5),1) med_usd, count(merchant_name) merch, count(tcat) tcat, count(*) n
  from tx group by 1 order by 1""").to_string())

print("\n=== G. Utilidad: 'compra en mi cuenta' -> ¿el cliente tiene tarjeta débito? ===")
print(q("""with c as (select customer_id, max((ptype like 'Cuenta%')::int) has_acc, max((ptype='Tarjeta Débito')::int) has_deb,
   max((ptype like 'Tarjeta%')::int) has_card, max((ptype like 'Cuenta%' and pstatus='Active')::int) acc_act,
   max((ptype='Tarjeta Débito' and pstatus='Active')::int) deb_act from pr group by 1)
  select count(*) n_cli, sum(has_acc) con_cuenta, sum(has_acc*has_deb) cuenta_y_debito, sum(has_acc*has_card) cuenta_y_tarjeta,
   sum(acc_act) cuenta_activa, sum(acc_act*deb_act) cuenta_act_y_deb_act from c""").to_string())
print(q("select ptype, count(*) n, round(avg((pstatus='Active')::int),3) p_active from pr group by 1 order by 1").to_string())
