# ids_15: las FK de sucursal que SÍ existen (pr.opening_branch_id, cp.related_branch_id, tx.branch_id) ¿son coherentes (mismo país) o sorteo uniforme?
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("select country, count(*)*1.0/350 shr from br group by 1"))
exp = con.execute("""select sum(a.s*b.s) from (select country, count(*)*1.0/350 s from br group by 1) a join (select country, count(*)*1.0/150000 s from cu group by 1) b
   on replace(a.country,'Mexico','México')=replace(b.country,'Mexico','México')""").fetchone()[0]
print('esperado_si_uniforme(mismo pais cliente-sucursal)=', round(exp,3))
print(q("""select 'pr.opening_branch_id' fk, count(*) n, avg((replace(b.country,'Mexico','México')=replace(c.country,'Mexico','México'))::int) same_ctry_cliente
    from pr p join br b on b.branch_id=p.opening_branch_id join cu c using(customer_id)
  union all select 'cp.related_branch_id', count(*), avg((replace(b.country,'Mexico','México')=replace(c.country,'Mexico','México'))::int)
    from cp join br b on b.branch_id=cp.related_branch_id join cu c using(customer_id)
  union all select 'tx.branch_id (vs pais tx)', count(*), avg((replace(b.country,'Mexico','México')=t.country)::int)
    from (select branch_id, country from tx where branch_id is not null using sample 200000) t join br b using(branch_id)
  union all select 'tx.branch_id (vs ciudad tx)', count(*), avg((b.city=t.city)::int)
    from (select branch_id, city from tx where branch_id is not null using sample 200000) t join br b using(branch_id)"""))
print(q("select branch_status, count(*) n from br group by 1"))
print(q("""select b.branch_status, count(*) n_tx, min(t.ts) first_tx, max(t.ts) last_tx, min(b.opened) min_open from (select branch_id, ts from tx where branch_id is not null using sample 300000) t join br b using(branch_id) group by 1"""))
print(q("""select avg((t.ts::date < b.opened)::int) tx_before_branch_opened from (select branch_id, ts from tx where branch_id is not null using sample 300000) t join br b using(branch_id)"""))
