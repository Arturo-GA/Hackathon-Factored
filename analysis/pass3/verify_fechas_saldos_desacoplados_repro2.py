# Verificacion independiente: fechas de tx vs apertura/vencimiento del producto (parte A)
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(title, s):
    print('==', title); print(con.execute(s).df().to_string(), '\n', flush=True)

S = "DATE '2023-06-17'"; E = "DATE '2026-06-17'"   # ventana (process_date)
N = "(date_diff('day', DATE '2023-06-17', DATE '2026-06-17') + 1)"  # 1097 dias inclusivos

q('relacion ts vs process_date', """select date_diff('day', ts::date, process_date) d, count(*) n from tx group by 1 order by 1""")

# A1. conteo antes de apertura con 3 definiciones
q('A1 antes de apertura (3 definiciones)', f"""select count(*) n,
   sum((t.ts::date < p.opened)::int) bo_tsdate, avg((t.ts::date < p.opened)::int) sh_tsdate,
   sum((t.process_date < p.opened)::int) bo_pdate, avg((t.process_date < p.opened)::int) sh_pdate,
   sum((t.ts < p.opened::timestamp)::int) bo_ts
   from tx t join pr p using(product_id)""")
# A2. por anio de apertura + esperado bajo fechas uniformes independientes de opened
q('A2 por anio de apertura: observado vs esperado-uniforme', f"""select year(p.opened) y, count(*) n,
   avg((t.ts::date < p.opened)::int) obs_sh,
   avg(greatest(0, least(1, date_diff('day', {S}, p.opened)::double / {N}))) exp_sh_unif,
   median(date_diff('day', t.ts::date, p.opened)) filter (where t.ts::date < p.opened) med_days_before
   from tx t join pr p using(product_id) group by 1 order by 1""")
q('A3 global: esperado vs observado y mediana dias antes', f"""select sum((t.ts::date < p.opened)::int) obs,
   sum(greatest(0, least(1, date_diff('day', {S}, p.opened)::double / {N}))) exp_unif,
   median(date_diff('day', t.ts::date, p.opened)) filter (where t.ts::date < p.opened) med_days_before
   from tx t join pr p using(product_id)""")
# A4. tasa de tx por producto-dia antes vs despues de abrir (productos abiertos dentro de la ventana)
q('A4 tasa tx por producto-dia antes vs despues de abrir (abiertos en ventana)', f"""
   with p as (select product_id, opened, date_diff('day', {S}, opened) dbef from pr where opened > {S} and opened <= {E}),
   c as (select t.product_id, sum((t.process_date < p.opened)::int) nb, sum((t.process_date >= p.opened)::int) na
         from tx t join p using(product_id) group by 1)
   select count(*) nprod, sum(coalesce(c.nb,0)) tx_before, sum(coalesce(c.na,0)) tx_after,
     sum(p.dbef) days_before, sum({N} - p.dbef) days_after,
     sum(coalesce(c.nb,0))/sum(p.dbef) rate_before, sum(coalesce(c.na,0))/sum({N} - p.dbef) rate_after,
     (sum(coalesce(c.nb,0))/sum(p.dbef)) / (sum(coalesce(c.na,0))/sum({N} - p.dbef)) rr_before_after
   from p left join c using(product_id)""")
q('A4b idem solo productos con >=1 tx', f"""
   with p as (select product_id, opened, date_diff('day', {S}, opened) dbef from pr where opened > {S} and opened <= {E}),
   c as (select t.product_id, sum((t.process_date < p.opened)::int) nb, sum((t.process_date >= p.opened)::int) na
         from tx t join p using(product_id) group by 1)
   select count(*) nprod, (sum(c.nb)/sum(p.dbef)) / (sum(c.na)/sum({N} - p.dbef)) rr_before_after
   from p join c using(product_id)""")
# A5. distribucion temporal por cohorte: share de tx por semestre de la ventana
q('A5 share de tx por semestre segun cohorte de apertura', f"""with a as (
   select case when p.opened < {S} then 'a_<2023-06' when year(p.opened)<=2024 then 'b_2023-06..2024' else 'c_2025-2026' end coh,
          least(5, date_diff('day', {S}, t.process_date) // 183) sem, count(*) n
   from tx t join pr p using(product_id) group by all)
   pivot (select coh, sem, round(n/sum(n) over (partition by coh),4) sh from a) on sem using first(sh) order by coh""")
# A6. volumen de tx por producto segun anio de apertura (no depende del tiempo abierto?)
q('A6 tx por producto (productos Active) segun anio apertura', """with c as (select product_id, count(*) n from tx group by 1)
   select year(p.opened) y, count(*) nprod, avg(coalesce(c.n,0)) tx_per_prod, avg((c.n is not null)::int) sh_with_tx
   from pr p left join c using(product_id) where p.pstatus='Active' group by 1 order by 1""")
# A7. vencimiento
q('A7 despues de vencimiento', f"""select count(*) n_con_exp, sum((t.ts::date > p.expires)::int) after_exp_tsdate,
   sum((t.process_date > p.expires)::int) after_exp_pdate,
   sum(greatest(0, least(1, date_diff('day', p.expires, {E})::double / {N}))) exp_unif
   from tx t join pr p using(product_id) where p.expires is not null""")
q('A8 tasa tx por producto-dia antes vs despues de vencer (vencen dentro de ventana)', f"""
   with p as (select product_id, expires, date_diff('day', {S}, expires) + 1 dvig from pr where expires >= {S} and expires < {E}),
   c as (select t.product_id, sum((t.process_date <= p.expires)::int) nv, sum((t.process_date > p.expires)::int) na
         from tx t join p using(product_id) group by 1)
   select count(*) nprod, sum(c.nv) tx_vigente, sum(c.na) tx_vencido,
     (sum(c.na)/sum({N} - p.dvig)) / (sum(c.nv)/sum(p.dvig)) rr_vencido_vs_vigente
   from p join c using(product_id)""")
# A9. productos con tx antes de apertura Y despues de vencer (vida util fuera de la ventana)
q('A9 tx antes de abrir o despues de vencer (union)', """select count(*) n,
   sum(((t.ts::date < p.opened) or (p.expires is not null and t.ts::date > p.expires))::int) fuera_vigencia
   from tx t join pr p using(product_id)""")
