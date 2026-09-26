# ids_27: identificación de tarjeta por últimos 4 dígitos (flujo "bloquear tarjeta"): ¿ambigüedad dentro del cliente? ¿BIN informativo?
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("""with c as (select customer_id, count(*) ncards, count(distinct right(product_number,4)) nl4 from pr where ptype like 'Tarjeta%' group by 1)
  select count(*) cust_with_cards, avg((ncards>1)::int) multi_card, max(ncards) max_cards, sum((nl4<ncards)::int) cust_with_last4_collision from c"""))
print(q("""with c as (select customer_id, count(*) ncards, count(distinct right(product_number,4)) nl4 from pr where ptype like 'Tarjeta%' and pstatus='Active' group by 1)
  select count(*) cust_active_cards, sum((nl4<ncards)::int) collision_active from c"""))
# ¿prefijo de 6 dígitos (BIN) se relaciona con rechazo/fraude?
print(q("""select substr(p.product_number,2,1) d2, count(*) n, round(avg((t.status='Declined')::int),4) decl, round(avg(t.fraud::int)*1000,3) fraud_mil
   from (select product_id, status, fraud from tx using sample 400000) t join pr p using(product_id) where p.ptype like 'Tarjeta%' group by 1 order by 1"""))
print(q("""select ptype, count(*) n, count(distinct substr(product_number,1,6)) n_bin from pr where ptype like 'Tarjeta%' group by 1"""))
