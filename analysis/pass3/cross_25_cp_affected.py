# H19: cp.affected_product_id (de otro cliente): el producto afectado muestra tx/fraude/rechazo alrededor del reclamo? vs producto aleatorio
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
con.execute("create temp table ap as select product_id, row_number() over (order by hash(product_id)) rn from pr where pstatus='Active'")
nact = con.execute("select count(*) from ap").fetchone()[0]
con.execute(f"""create temp table c as select cp.complaint_id, cp.ts, cp.subcategory, cp.affected_product_id pid, ap.product_id rnd
   from (select *, 1 + (hash(complaint_id) % {nact}) k from cp where affected_product_id is not null) cp join ap on ap.rn=cp.k""")
print(q("""select p.pstatus, count(*) n, round(count(*)*1.0/sum(count(*)) over(),3) shr from c join pr p on p.product_id=c.pid group by 1"""))
print(q("select pstatus, round(count(*)*1.0/sum(count(*)) over(),3) shr from pr group by 1"))
con.execute("create temp table t as select product_id, ts, status, fraud from tx where product_id in (select pid from c union select rnd from c)")
for col in ['pid','rnd']:
    print(col, q(f"""select c.subcategory, count(*) n,
      avg((exists(select 1 from t where t.product_id=c.{col} and t.ts between c.ts - interval 30 day and c.ts))::int) tx30,
      avg((exists(select 1 from t where t.product_id=c.{col} and t.ts between c.ts - interval 30 day and c.ts and t.status='Declined'))::int) dec30,
      avg((exists(select 1 from t where t.product_id=c.{col} and t.ts between c.ts - interval 90 day and c.ts and t.fraud))::int) fraud90
      from c join pr p on p.product_id=c.{col} where p.pstatus='Active' group by rollup(c.subcategory) order by 1"""))
