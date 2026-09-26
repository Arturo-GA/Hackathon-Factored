"""Verificacion independiente: status_iso_codes_inconsistent."""
import duckdb, pandas as pd, numpy as np, warnings
from scipy.stats import chi2_contingency
warnings.filterwarnings('ignore')
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

def cramer(df, r, c):
    ct = df.pivot_table(index=r, columns=c, values='n', aggfunc='sum').fillna(0)
    chi2 = chi2_contingency(ct.values, correction=False)[0]; n = ct.values.sum()
    return np.sqrt(chi2 / (n * (min(ct.shape) - 1)))

print("== ptype values ==")
print(q("select ptype, count(*) n from pr group by 1 order by 2 desc").to_string())

print("== status x code (todas) ==")
print(q("select status, coalesce(code,'NA') code, count(*) n from tx group by 1,2 order by 1,2")
      .pivot(index='status', columns='code', values='n').to_string())

# base: tx no aprobadas con join a producto
con.execute("""create temp table na as
 select t.status, coalesce(t.code,'NA') code, t.ttype, t.channel, p.ptype,
   (p.ptype ilike '%tarjeta%' or p.ptype ilike '%card%') is_card,
   t.ts, p.expires, p.opened, t.amount, p.bal,
   count(*) over () _dummy
 from tx t left join pr p using(product_id) where t.status <> 'Approved'""")
print("== denominadores ==")
print(q("""select count(*) n_no_aprob, sum(case when code<>'NA' then 1 else 0 end) n_con_codigo,
   sum(case when ptype is null then 1 else 0 end) sin_producto,
   sum(case when not is_card and code in ('14','54') then 1 else 0 end) card_code_non_card,
   sum(case when ttype='Deposit' then 1 else 0 end) dep_no_aprob,
   sum(case when ttype='Deposit' and code='51' then 1 else 0 end) dep_51,
   sum(case when ttype='Deposit' and code<>'NA' then 1 else 0 end) dep_con_codigo
 from na""").to_string())

print("== codigo por tarjeta/no tarjeta (no aprobadas con codigo) ==")
d = q("select is_card, code, count(*) n from na where code<>'NA' group by 1,2")
print(d.pivot(index='is_card', columns='code', values='n').to_string())
print("V(code|is_card) =", round(cramer(d, 'is_card', 'code'), 4))
for col in ['ttype', 'channel', 'ptype', 'status']:
    d = q(f"select {col}, code, count(*) n from na where code<>'NA' group by 1,2")
    print(f"V(code x {col}) =", round(cramer(d, col, 'code'), 4))
d = q("select ptype, code, count(*) n from na where code<>'NA' group by 1,2")
print((d.pivot(index='ptype', columns='code', values='n').pipe(lambda x: x.div(x.sum(1), axis=0))).round(3).to_string())
d = q("select ttype, code, count(*) n from na group by 1,2")
print(d.pivot(index='ttype', columns='code', values='n').to_string())

print("== 54 vs vencido; 51 vs monto>saldo (con denominadores limpios) ==")
print(q("""select t.status='Approved' aprob, coalesce(t.code,'NA') code, count(*) n,
  sum(case when p.expires is null then 1 else 0 end) exp_null,
  avg(case when t.ts > p.expires then 1.0 when p.expires is null then null else 0 end) venc_sobre_no_nulos,
  avg(case when t.ts > p.expires then 1.0 else 0 end) venc_sobre_todos,
  avg(case when t.amount > p.bal then 1.0 when p.bal is null then null else 0 end) monto_gt_saldo
 from tx t join pr p using(product_id) group by 1,2 order by 1,2""").round(4).to_string())
# restringido a tarjetas (donde 54 tendria sentido)
print("== solo tarjetas ==")
print(q("""select t.status='Approved' aprob, coalesce(t.code,'NA') code, count(*) n,
  avg(case when t.ts > p.expires then 1.0 when p.expires is null then null else 0 end) venc,
  avg(case when t.amount > p.bal then 1.0 when p.bal is null then null else 0 end) monto_gt_saldo
 from tx t join pr p using(product_id) where p.ptype ilike '%tarjeta%' group by 1,2 order by 1,2""").round(4).to_string())
# 51 vs monto>saldo solo en Purchase/Withdrawal/Transfer (debitos)
print("== debitos (Purchase/Withdrawal/Transfer/Payment) ==")
print(q("""select t.status='Approved' aprob, coalesce(t.code,'NA') code, count(*) n,
  avg(case when t.amount > p.bal then 1.0 when p.bal is null then null else 0 end) monto_gt_saldo
 from tx t join pr p using(product_id) where t.ttype in ('Purchase','Withdrawal','Transfer','Payment') group by 1,2 order by 1,2""").round(4).to_string())
