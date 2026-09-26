# Verificacion independiente: cross_ids_producto_ajenos
import duckdb, sys
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
part = sys.argv[1] if len(sys.argv) > 1 else 'all'

if part in ('all', 'cc'):
    print("== 1) cc.mentioned_products")
    print(q("select mentioned_products from cc where mentioned_products is not null limit 3"))
    con.execute("""create temp table m as
      select interaction_id, customer_id, cat, trim(x) pid, len(string_split(mentioned_products, ',')) k
      from (select interaction_id, customer_id, cat, mentioned_products, unnest(string_split(mentioned_products, ',')) x
            from cc where mentioned_products is not null)""")
    print(q("select count(*) n_ids, count(distinct pid) n_distinct, count(distinct interaction_id) n_contacts, min(k) kmin, max(k) kmax from m"))
    print(q("""select count(*) n, sum((p.product_id is not null)::int) n_exist,
               round(100*avg((p.product_id is not null)::int),3) pct_exist,
               sum((p.customer_id = m.customer_id)::int) n_own
             from m left join pr p on p.product_id = m.pid"""))
    print(q("""select m.cat, count(*) n, sum((p.product_id is not null)::int) n_exist, sum(coalesce((p.customer_id = m.customer_id)::int,0)) n_own
             from m left join pr p on p.product_id = m.pid group by 1 order by 1"""))
    # formato de IDs
    print(q("select left(pid,4) pref, length(pid) l, count(*) n from m group by 1,2 order by 3 desc limit 5"))
    print(q("select left(product_id,4) pref, length(product_id) l, count(*) n from pr group by 1,2 order by 3 desc limit 5"))
    print(q("select min(product_id) mn, max(product_id) mx from pr"))
    print(q("select min(pid) mn, max(pid) mx from m"))
    # estan en tx / cp?
    print(q("""select count(*) nd,
       sum((pid in (select product_id from tx))::int) in_tx,
       sum((pid in (select affected_product_id from cp where affected_product_id is not null))::int) in_cp
       from (select distinct pid from m)"""))
    # el dueno del producto existente mencionado: mismo pais que el cliente?
    print(q("""select count(*) n, round(avg((c1.country=c2.country)::int),3) same_country
             from m join pr p on p.product_id=m.pid join cu c1 on c1.customer_id=m.customer_id join cu c2 on c2.customer_id=p.customer_id"""))

if part in ('all', 'tx'):
    print("== 2) tx.product_id (referencia)")
    print(q("""select count(*) n, round(avg((p.product_id is not null)::int),4) ex, round(avg((p.customer_id=t.customer_id)::int),4) own
             from (select product_id, customer_id from tx using sample 300000) t left join pr p using(product_id)"""))

if part in ('all', 'de'):
    print("== 3) de.product_id")
    print(q("select count(*) n, count(product_id) n_pid, count(*) filter (where product_id is not null and customer_id is not null) n_pid_cust from de"))
    print(q("""select count(*) n, sum((p.product_id is not null)::int) n_exist,
               count(d.customer_id) n_with_cust,
               sum((p.customer_id = d.customer_id)::int) n_own,
               round(avg((cu.customer_id is not null)::int) filter (where d.customer_id is not null),4) cust_exists
             from (select product_id, customer_id from de where product_id is not null) d
             left join pr p using(product_id) left join cu on cu.customer_id=d.customer_id"""))
    print(q("select event_type, count(*) n from de where product_id is not null group by 1 order by 2 desc limit 8"))
    # pais del dueno vs pais del cliente del evento
    print(q("""select count(*) n, round(avg((c1.country=c2.country)::int),3) same_country
             from (select product_id, customer_id from de where product_id is not null and customer_id is not null) d
             join pr p using(product_id) join cu c1 on c1.customer_id=d.customer_id join cu c2 on c2.customer_id=p.customer_id"""))

if part in ('all', 'cp'):
    print("== 4) cp.affected_product_id")
    print(q("""select count(*) n, count(affected_product_id) nn, sum((p.product_id is not null)::int) n_exist,
               sum((p.customer_id=cp.customer_id)::int) n_own
             from cp left join pr p on p.product_id=cp.affected_product_id"""))
    print(q("""with a as (select p.pstatus, count(*) n from cp join pr p on p.product_id=cp.affected_product_id group by 1),
                  b as (select pstatus, count(*) n from pr group by 1)
             select a.pstatus, a.n, round(100*a.n/sum(a.n) over(),2) pct_cp, round(100*b.n/sum(b.n) over(),2) pct_pr
             from a join b using(pstatus) order by 1"""))
    print(q("""with a as (select p.ptype, count(*) n from cp join pr p on p.product_id=cp.affected_product_id group by 1),
                  b as (select ptype, count(*) n from pr group by 1)
             select a.ptype, a.n, round(100*a.n/sum(a.n) over(),2) pct_cp, round(100*b.n/sum(b.n) over(),2) pct_pr
             from a join b using(ptype) order by 1"""))
    # moneda del reclamo vs moneda del producto; pais cliente vs pais dueno
    print(q("""select round(avg((cp.currency=p.currency)::int),3) same_ccy, round(avg((c1.country=c2.country)::int),3) same_country,
               count(*) n from cp join pr p on p.product_id=cp.affected_product_id
               join cu c1 on c1.customer_id=cp.customer_id join cu c2 on c2.customer_id=p.customer_id"""))
    print(q("select count(*) n, count(distinct affected_product_id) nd from cp where affected_product_id is not null"))

if part in ('all', 'cpw'):
    print("== 5) cp: producto afectado vs aleatorio (tx 30d, Declined 30d, fraude 90d)")
    # comparador aleatorio: producto Active uniforme; mi propia semilla
    con.execute("select setseed(0.42)")
    con.execute("create temp table ap as select product_id, row_number() over (order by random()) rn from pr where pstatus='Active'")
    nact = con.execute("select count(*) from ap").fetchone()[0]
    con.execute(f"""create temp table c as
       select x.complaint_id, x.ts, x.subcategory, x.pid, ap.product_id rnd
       from (select complaint_id, ts, subcategory, affected_product_id pid,
                    1 + (hash(complaint_id || 'v2') % {nact})::bigint k
             from cp where affected_product_id is not null) x join ap on ap.rn = x.k""")
    con.execute("create temp table cand as select pid p from c union select rnd from c")
    con.execute("""create temp table t as select product_id, ts, status, fraud from tx
                   where product_id in (select p from cand)""")
    print("filas tx candidatas:", con.execute("select count(*) from t").fetchone()[0])
    for col in ['pid', 'rnd']:
        con.execute(f"""create or replace temp table f_{col} as
          select c.complaint_id, c.subcategory,
            max((t.ts between c.ts - interval 30 day and c.ts)::int) tx30,
            max((t.ts between c.ts - interval 30 day and c.ts and t.status='Declined')::int) dec30,
            max((t.ts between c.ts - interval 90 day and c.ts and t.fraud)::int) fr90
          from c join pr p on p.product_id=c.{col} and p.pstatus='Active'
          left join t on t.product_id=c.{col} and t.ts between c.ts - interval 90 day and c.ts
          group by 1,2""")
    sel = "count(*) n, round(100*avg(coalesce(tx30,0)),2) tx30, round(100*avg(coalesce(dec30,0)),3) dec30, round(100*avg(coalesce(fr90,0)),3) fr90, sum(coalesce(fr90,0)) nfr"
    print(q(f"""select 'afectado' g, {sel} from f_pid union all select 'aleatorio', {sel} from f_rnd"""))
    print(q(f"""select 'afectado' g, {sel} from f_pid where subcategory ilike '%no reconocido%'
               union all select 'aleatorio', {sel} from f_rnd where subcategory ilike '%no reconocido%'"""))
    print(q("select subcategory, count(*) n from cp group by 1 order by 2 desc limit 30"))

if part in ('all', 'tr'):
    print("== 6) transcripts: producto mencionado vs productos del cliente")
    print(q("select json_extract_string(mentioned_entities,'$.products') prod, count(*) n from tr group by 1 order by 2 desc limit 10"))
    con.execute("""create temp table tt as select transcript_id, customer_id, json_extract_string(mentioned_entities,'$.products') prod from tr""")
    con.execute("create temp table own as select distinct customer_id, ptype from pr")
    print(q("""select tt.prod, count(*) n, round(100*avg((o.customer_id is not null)::int),2) pct_has
             from tt left join own o on o.customer_id=tt.customer_id and o.ptype=tt.prod
             where tt.prod is not null group by 1 order by 2 desc"""))
    # base: todos los clientes, y clientes con transcript
    print(q("""select p.ptype, round(100*avg((o.customer_id is not null)::int),2) pct_all_cust
             from (select distinct prod ptype from tt where prod is not null) p cross join (select customer_id from cu) c
             left join own o on o.customer_id=c.customer_id and o.ptype=p.ptype group by 1"""))
    print(q("""select p.ptype, round(100*avg((o.customer_id is not null)::int),2) pct_tr_cust
             from (select distinct prod ptype from tt where prod is not null) p cross join (select customer_id from tt group by 1) c
             left join own o on o.customer_id=c.customer_id and o.ptype=p.ptype group by 1"""))
