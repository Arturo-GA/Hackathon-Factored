# Verificador escéptico: cross_moneda_por_pais
import duckdb, sys
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
sec = sys.argv[1] if len(sys.argv) > 1 else 'all'

if sec in ('all', 'A'):
    print('== A: variantes de cu.country y moneda de producto')
    print(q("select country, count(*) n from cu group by 1 order by 2 desc"))
    print(q("select c.country, p.currency, count(*) n from pr p join cu c using(customer_id) group by 1,2 order by 1,2"))
    # pais de apertura (sucursal) vs moneda: ¿es el pais del cliente o de la sucursal?
    print(q("""select c.country cli, b.country suc, p.currency, count(*) n from pr p join cu c using(customer_id)
       left join br b on b.branch_id=p.opening_branch_id group by 1,2,3 order by 1,2,3"""))

if sec in ('all', 'B'):
    print('== B: USD en CO/AR: ¿depende de algo? (ptype, segmento, status, canal, año apertura, app)')
    for col in ['p.ptype', 'c.segment', 'p.pstatus', 'p.opening_channel', 'year(p.opened)', 'p.app', 'c.cstatus', "ntile(5) over (order by c.income)"]:
        print(col, q(f"""select k, count(*) n, round(avg(u),4) usd from (select {col} k, (p.currency='USD')::int u from pr p join cu c using(customer_id) where c.country in ('Colombia','Argentina')) group by 1 order by 1"""))
    # nivel cliente: ¿USD asignado por producto (Bernoulli iid) o por cliente?
    print(q("""with t as (select c.customer_id, count(*) np, sum((p.currency='USD')::int) nu from pr p join cu c using(customer_id)
       where c.country in ('Colombia','Argentina') group by 1)
       select np, count(*) ncli, round(avg(nu),3) mean_usd, round(avg((nu=0)::int),4) p_all_local, round(power(0.9,np),4) p_iid_all_local,
              round(avg((nu=np)::int),4) p_all_usd, round(power(0.1,np),5) p_iid_all_usd
       from t group by 1 order by 1 limit 8"""))

if sec in ('all', 'C'):
    print('== C: moneda de tx vs pais del cliente y pais de la tx')
    print(q("""select c.country, t.currency, count(*) n from tx t join cu c using(customer_id) group by 1,2 order by 1,2"""))
    print(q("""select c.country cli, t.country txc, t.currency, count(*) n from tx t join cu c using(customer_id)
       where t.country is distinct from c.country group by 1,2,3 order by 4 desc limit 15"""))
    print(q("select avg((t.currency=p.currency)::int) eq_prod from tx t join pr p using(product_id)"))

if sec in ('all', 'D'):
    print('== D: amount_usd / amount en tabla completa')
    print(q("""select currency, count(*) n, round(avg((amount_usd is null)::int),4) pnull,
       round(min(amount_usd/amount),8) mn, round(max(amount_usd/amount),8) mx,
       round(avg((abs(amount_usd - round(amount*case currency when 'COP' then 1/4000.0 when 'ARS' then 1/350.0 else 1 end,2))<=0.011)::int),5) eq_const
       from tx where amount<>0 group by 1"""))
    print(q("""select currency, round(avg((amount_usd is null)::int),4) pnull, status, count(*) n from tx group by 1,3 order by 1,3"""))
    print(q("""select src, dst, round(avg(rate),7) mean, round(min(rate),7) mn, round(max(rate),7) mx, round(stddev(rate)/avg(rate),4) cv, count(*) n
       from fx where dst='USD' or src='USD' group by 1,2 order by 1,2"""))
    # ¿la constante coincide con el nivel medio de fx? (base del generador)
    print(q("select 1/4000.0 cop_const, 1/350.0 ars_const, 1/17.0 mxn_ref"))

if sec in ('all', 'E'):
    print('== E: reclamos: moneda y monto')
    print(q("""select c.country, cp.currency, count(*) n, round(count(*)*1.0/sum(count(*)) over (partition by c.country),4) shr
       from cp join cu c using(customer_id) group by 1,2 order by 1,2"""))
    print(q("""select currency, count(*) n, round(min(claimed),2) mn, round(quantile_cont(claimed,0.25),1) q25, round(median(claimed),1) med,
       round(quantile_cont(claimed,0.75),1) q75, round(max(claimed),2) mx, round(avg((claimed is null)::int),4) pnull from cp group by 1 order by 1"""))
    # moneda del reclamo vs moneda de los productos del propio cliente
    print(q("""with pc as (select customer_id, list(distinct currency) cs from pr group by 1)
       select cp.currency, count(*) n, round(avg(list_contains(pc.cs, cp.currency)::int),4) in_own_prod
       from cp join pc using(customer_id) where cp.currency is not null group by 1 order by 1"""))
    # moneda del reclamo vs moneda del producto afectado (de otro cliente)
    print(q("""select cp.currency, round(avg((cp.currency=p.currency)::int),4) eq_affected, count(p.product_id) n
       from cp left join pr p on p.product_id=cp.affected_product_id where cp.currency is not null group by 1 order by 1"""))
    # claimed por categoria / subcategoria (¿cargo no reconocido tiene montos distintos?)
    print(q("""select category, count(*) n, round(avg((claimed is null)::int),3) pnull, round(median(claimed),1) med, round(avg(claimed),1) mean
       from cp group by 1 order by 2 desc limit 10"""))
