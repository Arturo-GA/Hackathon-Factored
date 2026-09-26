# Verificador esceptico: cross_tx_por_producto_activo
import duckdb, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
P = lambda s: print(q(s).to_string(), flush=True)

# A) tautologia: tx.customer_id = pr.customer_id? huerfanas?
print("== A) consistencia tx-pr ==")
P("""select count(*) ntx, sum((p.product_id is null)::int) huerfanas, sum((p.customer_id<>t.customer_id)::int) cliente_distinto,
     sum((p.pstatus<>'Active')::int) no_active, sum((p.currency<>t.currency)::int) moneda_distinta
     from tx t left join pr p using(product_id)""")
# B) conteos por producto, por pstatus
con.execute("""create temp table tp as select p.product_id, p.customer_id, p.ptype, p.pstatus, p.opened, p.expires, p.last_tx, p.bal, p.credit_limit, p.app, p.currency,
   coalesce(t.n,0) n, t.f, t.l from pr p left join (select product_id, count(*) n, min(ts) f, max(ts) l from tx group by 1) t using(product_id)""")
print("== B) por pstatus ==")
P("select pstatus, count(*) np, sum(n) ntx, round(avg(n),3) mean, round(var_samp(n)/nullif(avg(n),0),3) disp, min(n) mn, max(n) mx from tp group by 1 order by 1")
nact = q("select count(*) c from tp where pstatus='Active'").c[0]
ntx = q("select count(*) c from tx").c[0]
print(f"ntx/nactive = {ntx/nact:.4f}  (si asignacion uniforme multinomial, var/mean esperado = 1-1/N = {1-1/nact:.6f})")
# C) depende de atributos del producto? opened, expires, currency, app, bal
print("== C) media tx por producto Active segun atributos ==")
P("""select case when opened < date '2023-06-17' then '<ventana' when opened <= date '2026-06-17' then cast(year(opened) as varchar) else '>fin' end g,
   count(*) np, round(avg(n),3) mean from tp where pstatus='Active' group by 1 order by 1""")
P("select currency, count(*) np, round(avg(n),3) mean from tp where pstatus='Active' group by 1 order by 1")
P("select app, count(*) np, round(avg(n),3) mean from tp where pstatus='Active' group by 1 order by 1")
P("select ntile(5) over (order by bal) qb, count(*) np, round(avg(n),3) mean from tp where pstatus='Active' group by all order by 1") if False else None
P("select qb, count(*) np, round(avg(n),3) mean from (select n, ntile(5) over (order by bal) qb from tp where pstatus='Active') group by 1 order by 1")
# D) tx antes de apertura / despues de vencimiento (utilidad de la 'linea base mensual')
print("== D) tx fuera de vida del producto ==")
P("""select round(avg((t.ts < p.opened)::int),4) antes_apertura, round(avg((t.ts > p.expires)::int),4) despues_venc, count(*) n
     from tx t join pr p using(product_id)""")
P("""select case when p.opened > date '2026-01-01' then 'abierto_2026' when p.opened > date '2023-06-17' then 'abierto_en_ventana' else 'antes' end g,
     count(*) ntx, round(avg((t.ts < p.opened)::int),4) antes_apertura from tx t join pr p using(product_id) group by 1 order by 1""")
# E) last_tx de pr vs max(ts) real
print("== E) pr.last_tx vs max(tx.ts) ==")
P("""select count(*) np, sum((last_tx is null)::int) null_lasttx, sum((l is not null and cast(last_tx as date)=cast(l as date))::int) iguales,
     round(avg(abs(date_diff('day', cast(last_tx as date), cast(l as date)))),1) dif_media_dias from tp where pstatus='Active'""")
