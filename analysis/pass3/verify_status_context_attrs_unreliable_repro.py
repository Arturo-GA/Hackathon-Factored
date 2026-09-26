"""Verificacion independiente: status_context_attrs_unreliable.
A) ts de tx vs pr.opened / pr.expires / cu.registration_date (uniformidad en la ventana)
B) pr.last_tx vs max(ts) real
C) lat/lon vs pais de residencia y pais de la tx
D) ciudad/coords de la sucursal vs tx
"""
import duckdb, pandas as pd, warnings
warnings.filterwarnings('ignore')
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width', 250)

print("== ventana tx ==")
print(q("select min(ts) mn, max(ts) mx, count(*) n from tx").to_string())

W0, W1 = "timestamp '2023-06-17'", "timestamp '2026-06-18'"
WLEN = f"epoch({W1})-epoch({W0})"

print("\n== A1: tx antes de opened por anio de apertura, con esperado bajo ts uniforme en ventana ==")
print(q(f"""
select year(p.opened) y_open, count(*) n,
  round(avg(case when t.ts < cast(p.opened as timestamp) then 1 else 0 end),4) obs_antes_apertura,
  round(avg(greatest(0, least(1, (epoch(cast(p.opened as timestamp)) - epoch({W0}))/({WLEN})))),4) esperado_uniforme
from tx t join pr p using(product_id) group by 1 order by 1""").to_string())
print(q(f"""
select count(*) n,
  round(avg(case when t.ts < cast(p.opened as timestamp) then 1 else 0 end),4) antes_apertura,
  round(avg(case when p.expires is not null and t.ts > cast(p.expires as timestamp) then 1 else 0 end),4) despues_venc,
  round(avg(case when p.expires is null then 1 else 0 end),4) expires_nulo,
  round(avg(case when t.ts < u.registration_date then 1 else 0 end),4) antes_registro,
  round(avg(case when t.ts < u.registration_date or t.ts < cast(p.opened as timestamp) then 1 else 0 end),4) antes_reg_o_apert
from tx t join pr p using(product_id) join cu u on u.customer_id=t.customer_id""").to_string())

print("\n== A2: por status de tx ==")
print(q("""
select t.status, count(*) n,
  round(avg(case when t.ts < cast(p.opened as timestamp) then 1 else 0 end),4) antes_apertura,
  round(avg(case when t.ts > cast(p.expires as timestamp) then 1 else 0 end),4) despues_venc,
  round(avg(case when t.ts < u.registration_date then 1 else 0 end),4) antes_registro
from tx t join pr p using(product_id) join cu u on u.customer_id=t.customer_id group by 1 order by 1""").to_string())

print("\n== A3: densidad de tx antes vs despues de abrir (productos abiertos dentro de la ventana) ==")
# tasa tx/dia antes y despues de la apertura, agregada; si la apertura no importa, razon ~1
print(q(f"""
with p2 as (select product_id, opened from pr where opened > date '2023-07-17' and opened < date '2026-05-17'),
 c as (select p2.product_id, p2.opened,
          sum(case when t.ts < cast(p2.opened as timestamp) then 1 else 0 end) n_antes,
          sum(case when t.ts >= cast(p2.opened as timestamp) then 1 else 0 end) n_despues
       from tx t join p2 using(product_id) group by 1,2)
select year(opened) y, count(*) n_prod, sum(n_antes) n_antes, sum(n_despues) n_desp,
  sum(date_diff('day', date '2023-06-17', opened)) dias_antes,
  sum(date_diff('day', opened, date '2026-06-18')) dias_desp,
  round((sum(n_despues)/sum(date_diff('day', opened, date '2026-06-18'))) /
        (sum(n_antes)/sum(date_diff('day', date '2023-06-17', opened))),3) razon_tasa_desp_vs_antes
from c group by 1 order by 1""").to_string())

print("\n== A4: por anio de registro del cliente ==")
print(q(f"""
select year(u.registration_date) y_reg, count(*) n,
  round(avg(case when t.ts < u.registration_date then 1 else 0 end),4) obs_antes_reg,
  round(avg(greatest(0, least(1, (epoch(u.registration_date) - epoch({W0}))/({WLEN})))),4) esperado_uniforme
from tx t join cu u on u.customer_id=t.customer_id group by 1 order by 1""").to_string())

print("\n== A5: por anio de vencimiento ==")
print(q(f"""
select year(p.expires) y_exp, count(*) n,
  round(avg(case when t.ts > cast(p.expires as timestamp) then 1 else 0 end),4) obs_desp_venc,
  round(avg(greatest(0, least(1, (epoch({W1}) - epoch(cast(p.expires as timestamp)))/({WLEN})))),4) esperado_uniforme
from tx t join pr p using(product_id) group by 1 order by 1""").to_string())

print("\n== B: pr.last_tx vs max(ts) real ==")
print(q("""
with m as (select product_id, max(ts) mx from tx group by 1)
select count(*) n_prod_con_tx,
  round(avg(case when p.last_tx is null then 1 else 0 end),4) lt_nulo,
  round(avg(case when cast(p.last_tx as date)=cast(m.mx as date) then 1 else 0 end),5) lt_misma_fecha,
  sum(case when cast(p.last_tx as date)=cast(m.mx as date) then 1 else 0 end) n_misma_fecha,
  round(avg(case when p.last_tx = m.mx then 1 else 0 end),5) lt_igual_exacto,
  median(date_diff('day', m.mx, p.last_tx)) med_dif_dias,
  round(avg(case when abs(date_diff('day', m.mx, p.last_tx))<=7 then 1 else 0 end),4) dentro_7d,
  round(avg(case when p.last_tx > m.mx then 1 else 0 end),4) lt_posterior,
  round(avg(case when p.last_tx < m.mx then 1 else 0 end),4) lt_anterior
from m join pr p using(product_id)""").to_string())
print(q("""select count(*) n_pr, round(avg(case when last_tx is null then 1 else 0 end),4) lt_nulo_todos,
  min(last_tx) mn, max(last_tx) mx from pr""").to_string())

print("\n== C: cajas geograficas lat/lon ==")
box = """case when abs(t.lat)<=1.0001 and abs(t.lon)<=1.0001 then 'caja(0±1,0±1)'
 when abs(t.lat)<=2 and abs(t.lon)<=2 then 'caja(0±2)'
 when t.lat between 14 and 33 and t.lon between -118 and -86 then 'MX'
 when t.lat between -5 and 13 and t.lon between -80 and -66 then 'CO'
 when t.lat between -56 and -21 and t.lon between -74 and -53 then 'AR' else 'otro' end"""
df = q(f"""select u.country cu_pais, t.country tx_pais, {box} caja, count(*) n
 from tx t join cu u on u.customer_id=t.customer_id where t.lat is not null group by 1,2,3""")
df['tipo'] = (df.cu_pais == df.tx_pais).map({True: 'local', False: 'extranjera'})
print(df.groupby(['cu_pais', 'tipo', 'caja']).n.sum().unstack().fillna(0).astype(int).to_string())
print(q("""select u.country, count(*) n, round(min(t.lat),3) lat_mn, round(max(t.lat),3) lat_mx,
  round(min(t.lon),3) lon_mn, round(max(t.lon),3) lon_mx, round(stddev(t.lat),3) sd_lat, round(stddev(t.lon),3) sd_lon
 from tx t join cu u on u.customer_id=t.customer_id where t.lat is not null group by 1 order by 1""").to_string())
print("lat/lon no nulos por canal:")
print(q("select channel, count(*) n, round(avg(case when lat is not null then 1 else 0 end),3) lat_nn from tx group by 1 order by 1").to_string())
print("tx.country vs pais del cliente (lat no nulo):")
print(q("""select u.country cu, t.country tx, count(*) n from tx t join cu u on u.customer_id=t.customer_id
 where t.lat is not null group by 1,2 order by 1,3 desc""").to_string())

print("\n== D: sucursal vs tx ==")
print(q("""select u.country cu_pais, count(*) n,
  round(avg(case when t.city=b.city then 1 else 0 end),4) misma_ciudad,
  round(avg(case when t.country=b.country then 1 else 0 end),4) mismo_pais,
  round(median(sqrt(power(t.lat-b.lat,2)+power(t.lon-b.lon,2))),2) med_dist_grados
 from tx t join br b using(branch_id) join cu u on u.customer_id=t.customer_id
 where t.branch_id is not null group by rollup(1) order by 1""").to_string())
print(q("""select round(avg(case when t.city=b.city then 1 else 0 end),4) misma_ciudad_todos,
  round(median(sqrt(power(t.lat-b.lat,2)+power(t.lon-b.lon,2))),2) med_dist_todos,
  count(*) n
 from tx t join br b using(branch_id) where t.branch_id is not null""").to_string())
print(q("""select b.country, round(min(b.lat),2) lat_mn, round(max(b.lat),2) lat_mx, round(min(b.lon),2) lon_mn, round(max(b.lon),2) lon_mx, count(*) n from br b group by 1""").to_string())

print("\n== E: detalles ==")
print(q("""select count(*) n_lat_nn, sum(case when lon is null then 1 else 0 end) lon_nulo_con_lat from tx where lat is not null""").to_string())
print(q("""select round(avg(case when t.ts > cast(p.expires as timestamp) then 1 else 0 end),4) desp_venc_entre_con_expires, count(*) n
 from tx t join pr p using(product_id) where p.expires is not null""").to_string())
print("centro de la caja por pais de residencia y por ciudad del cliente (top):")
print(q("""select u.country, u.city, count(*) n, round(avg(t.lat),2) lat_m, round(avg(t.lon),2) lon_m
 from tx t join cu u on u.customer_id=t.customer_id where t.lat is not null and t.lon is not null
 group by 1,2 qualify row_number() over (partition by u.country order by count(*) desc)<=3 order by 1,3 desc""").to_string())
print("sucursales cerca de (0,0):")
print(q("""select country, count(*) n, sum(case when abs(lat)<=1 and abs(lon)<=1 then 1 else 0 end) null_island,
  sum(case when lat is null then 1 else 0 end) lat_nulo from br group by 1""").to_string())
