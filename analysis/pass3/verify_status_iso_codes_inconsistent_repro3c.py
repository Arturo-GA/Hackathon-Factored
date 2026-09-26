"""Verificacion independiente (intento 3, parte 3): status_iso_codes_inconsistent.
Codigo 54 vs producto vencido (ts > expires) y codigo 51 vs monto > saldo/disponible."""
import duckdb, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

print("== tipos de columnas ==")
print(q("select column_name, data_type from information_schema.columns where table_name in ('tx','pr') and column_name in ('ts','expires','opened','amount','bal','credit_limit','code','status')").to_string())

J = "tx t join pr p on t.product_id = p.product_id"
GRP = """case when t.status='Approved' then 'Aprobada' else 'NoAprob_'||coalesce(t.code,'NA') end"""

print("\n== (A) replica original: todas las tx, ts>expires con expires nulo=0 ==")
print(q(f"""select {GRP} g, count(*) n,
  avg(case when t.ts > p.expires then 1.0 else 0 end) venc_nulo0,
  avg(case when p.expires is null then null when t.ts > p.expires then 1.0 else 0 end) venc_solo_no_nulos,
  avg(case when t.amount > p.bal then 1.0 else 0 end) monto_gt_bal
  from {J} group by 1 order by 1""").round(4).to_string())

print("\n== (B) solo tarjetas con expires no nulo ==")
print(q(f"""select {GRP} g, count(*) n,
  avg(case when t.ts > p.expires then 1.0 else 0 end) venc,
  avg(case when t.ts::date > p.expires + interval 30 day then 1.0 else 0 end) venc_30d
  from {J} where p.ptype like 'Tarjeta%' and p.expires is not null group by 1 order by 1""").round(4).to_string())

print("\n== (B2) direccion inversa en tarjetas: vencido -> tasa no aprobada y tasa de 54 ==")
d = q(f"""select (t.ts > p.expires) vencido, count(*) n,
  avg(case when t.status<>'Approved' then 1.0 else 0 end) p_no_aprob,
  avg(case when t.status='Declined' then 1.0 else 0 end) p_declined,
  avg(case when t.status<>'Approved' and t.code='54' then 1.0 else 0 end) p_54,
  sum(case when t.status<>'Approved' and t.code='54' then 1 else 0 end) n_54,
  sum(case when t.status='Approved' then 1 else 0 end) n_aprob
  from {J} where p.ptype like 'Tarjeta%' and p.expires is not null group by 1 order by 1""")
print(d.round(5).to_string())
r = d.set_index('vencido')
print("RR no aprob (vencido/no) =", round(r.loc[True, 'p_no_aprob'] / r.loc[False, 'p_no_aprob'], 3),
      "| RR 54 (vencido/no) =", round(r.loc[True, 'p_54'] / r.loc[False, 'p_54'], 3),
      "| % tx vencidas aprobadas =", round(r.loc[True, 'n_aprob'] / r.loc[True, 'n'], 4))

print("\n== (B3) cuanto tiempo despues del vencimiento ocurren las tx aprobadas en tarjetas vencidas ==")
print(q(f"""select quantile_cont(date_diff('day', p.expires, t.ts::date), [0.1,0.5,0.9]) q_dias, count(*) n
  from {J} where p.ptype like 'Tarjeta%' and t.status='Approved' and t.ts > p.expires""").to_string())

print("\n== (C) escala: monto vs saldo por moneda y ptype (medianas) ==")
print(q(f"""select p.ptype, t.currency, count(*) n, median(t.amount) med_amount, median(p.bal) med_bal,
  median(p.credit_limit) med_cl, avg(case when p.bal<0 then 1.0 else 0 end) bal_neg,
  avg(case when p.credit_limit is not null and p.bal>p.credit_limit then 1.0 else 0 end) bal_gt_cl
  from {J} group by 1,2 order by 1,2""").round(3).to_string())

print("\n== (D) 51 vs monto>saldo (replica) y con 'disponible' (cuentas/debito: bal; credito: limite-bal) ==")
AV = """case when p.ptype='Tarjeta Crédito' then p.credit_limit - p.bal
             when p.ptype in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Débito') then p.bal else null end"""
print(q(f"""select {GRP} g, count(*) n,
  avg(case when t.amount > p.bal then 1.0 else 0 end) monto_gt_bal_todas,
  avg(case when ({AV}) is null then null when t.amount > ({AV}) then 1.0 else 0 end) monto_gt_disp_debitos
  from {J} where t.ttype in ('Purchase','Withdrawal','Transfer','Payment') group by 1 order by 1""").round(4).to_string())

print("\n== (D2) direccion inversa en debitos con disponible: monto>disponible -> tasa no aprob y 51 ==")
d = q(f"""select (t.amount > ({AV})) excede, count(*) n,
  avg(case when t.status<>'Approved' then 1.0 else 0 end) p_no_aprob,
  avg(case when t.status<>'Approved' and t.code='51' then 1.0 else 0 end) p_51
  from {J} where t.ttype in ('Purchase','Withdrawal','Transfer','Payment') and ({AV}) is not null group by 1 order by 1""")
print(d.round(5).to_string())
r = d.set_index('excede')
print("RR no aprob (excede/no) =", round(r.loc[True, 'p_no_aprob'] / r.loc[False, 'p_no_aprob'], 3),
      "| RR 51 (excede/no) =", round(r.loc[True, 'p_51'] / r.loc[False, 'p_51'], 3))

print("\n== (D3) por moneda: % monto>bal en no aprobadas 51 vs aprobadas ==")
print(q(f"""select t.currency, {GRP} g, count(*) n, avg(case when t.amount > p.bal then 1.0 else 0 end) monto_gt_bal
  from {J} where (t.status='Approved' or t.code='51') group by 1,2 order by 1,2""").round(4).to_string())
