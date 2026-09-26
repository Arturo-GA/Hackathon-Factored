# Verificacion independiente: cross_identidad_no_unica
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: print(con.execute(s).fetchdf().to_string(), flush=True)

print("== 1. Unicidad de llaves en cu ==")
q("""select count(*) n, count(distinct customer_id) ncid, count(distinct document_number) ndoc,
  count(document_number) doc_nonnull, count(distinct email) nemail_distinct_nonnull, count(email) email_nonnull,
  count(*)-count(email) email_null, count(distinct lower(trim(email))) nemail_norm,
  count(distinct mobile_phone) nmob, count(mobile_phone) mob_nonnull,
  count(distinct (document_type, document_number)) ndoctype_doc
  from cu""")

print("== 2. Emails compartidos (no nulos, normalizados) ==")
con.execute("""create temp table em as select lower(trim(email)) e, count(*) k,
  count(distinct lower(first_name)||'|'||lower(last_name)) nnames, count(distinct country) nctry
  from cu where email is not null group by 1""")
q("""select count(*) emails_distintos, sum(k) clientes_con_email,
  count(*) filter (where k>1) emails_compartidos, sum(k) filter (where k>1) clientes_en_compartidos,
  round(sum(k) filter (where k>1)*1.0/150000,4) frac_sobre_150k,
  round(sum(k) filter (where k>1)*1.0/sum(k),4) frac_sobre_con_email,
  max(k) max_k,
  round(avg((nnames>1)::int) filter (where k>1),4) frac_grupos_nombres_distintos,
  round(avg((nnames=k)::int) filter (where k>1),4) frac_grupos_todos_distintos,
  round(avg((nctry>1)::int) filter (where k>1),4) frac_grupos_multi_pais
  from em""")
q("select k, count(*) n_emails from em group by 1 order by 1 limit 12")

print("== 3. Patron del email: local part vs nombre ==")
q("""select split_part(email,'@',2) dom, count(*) n from cu where email is not null group by 1 order by 2 desc limit 8""")
q("""select first_name, last_name, email from cu using sample 8 rows (reservoir, 7)""")
# posibles patrones
q("""with t as (select lower(split_part(email,'@',1)) lp,
   lower(strip_accents(first_name)) f, lower(strip_accents(last_name)) l from cu where email is not null)
  select count(*) n,
   round(avg((lp like left(f,1)||'%')::int),4) empieza_inicial,
   round(avg((lp like left(f,1)||replace(l,' ','')||'%')::int),4) inicial_apellido_prefijo,
   round(avg((lp = left(f,1)||replace(l,' ',''))::int),4) inicial_apellido_exacto,
   round(avg((lp like '%'||replace(split_part(l,' ',1),' ','')||'%')::int),4) contiene_1er_apellido,
   round(avg((lp like f||'%')::int),4) empieza_nombre
  from t""")
q("""with t as (select lower(split_part(email,'@',1)) lp,
   lower(strip_accents(first_name)) f, lower(strip_accents(last_name)) l from cu where email is not null)
  select lp, f, l from t where not (lp like left(f,1)||'%') using sample 8 rows (reservoir, 3)""")

print("== 4. Lookup por email: cuantos clientes devuelve ==")
q("""select round(avg((k>1)::int),4) frac_lookups_ambiguos_por_cliente from cu c join em on lower(trim(c.email))=em.e""")

print("== 5. Prefijo movil / fijo por pais ==")
q("""select country, coalesce(split_part(mobile_phone,' ',1),'<NULL>') pref, count(*) n,
   round(count(*)*1.0/sum(count(*)) over (partition by country),4) shr from cu group by 1,2 order by 1,3 desc""")
q("""select country, coalesce(regexp_extract(mobile_phone,'^\+?(\d{1,3})',1),'<NULL>') pref2, count(*) n from cu group by 1,2 order by 1,3 desc""")
q("""select country, coalesce(split_part(landline_phone,' ',1),'<NULL>') pref, count(*) n from cu group by 1,2 order by 1,3 desc""")
q("""select country, mobile_phone, landline_phone, city from cu using sample 9 rows (reservoir, 11)""")
print("-- telefonos compartidos")
q("""with p as (select mobile_phone, count(*) k from cu where mobile_phone is not null group by 1)
  select count(*) distintos, count(*) filter (where k>1) compartidos, sum(k) filter (where k>1) clientes, max(k) from p""")

print("== 6. session_id en de (muestra hash%5=2, ~20%) ==")
con.execute("""create temp table s as select session_id, count(*) n, count(distinct customer_id) ncust,
  sum((customer_id is null)::int) nanon, count(distinct ip_address) nip
  from de where hash(session_id)%5=2 group by 1""")
q("""select count(*) sesiones, sum(n) eventos, sum(nanon) eventos_anon,
  round(sum(nanon)*1.0/sum(n),4) frac_anon,
  sum((ncust>1)::int) sesiones_multicliente,
  round(avg((ncust=0)::int),4) frac_sesiones_todo_anon,
  round(avg((ncust=1 and nanon>0)::int),4) frac_sesiones_mixtas,
  round(sum(nanon) filter (where ncust=1)*1.0/sum(nanon),4) frac_anon_imputables,
  max(nip) max_ip_por_sesion, round(avg((nip>1)::int),4) frac_ses_multi_ip
  from s""")
q("select ncust, count(*) from s group by 1 order by 1")
print("-- sesiones totales (conteo aproximado)")
q("select approx_count_distinct(session_id) ses_total, count(*) filter (where session_id is null) ev_sin_sesion from de")
print("-- IP -> clientes (muestra hash%20=3)")
con.execute("""create temp table ip as select ip_address, count(*) n, count(distinct customer_id) ncust, count(distinct session_id) nses
  from de where hash(ip_address)%20=3 group by 1""")
q("""select count(*) ips, round(avg(n),2) ev, round(avg(nses),2) ses_por_ip, round(avg((ncust>1)::int),4) frac_ip_multicliente, max(ncust) max_cli from ip""")
