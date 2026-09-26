# Verificacion independiente: cross_moneda_por_pais
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(s):
    print(con.execute(s).fetchdf().to_string(), flush=True)

print("== 1. pr.currency por pais del cliente")
q("""select c.country, p.currency, count(*) n,
       round(100.0*count(*)/sum(count(*)) over (partition by c.country),2) pct
     from pr p join cu c on c.customer_id=p.customer_id group by 1,2 order by 1,2""")
q("select count(*) n_pr, count(c.customer_id) n_join from pr p left join cu c on c.customer_id=p.customer_id")

print("== 1b. %USD por ptype (Colombia/Argentina)")
q("""select c.country, p.ptype, count(*) n, round(100*avg((p.currency='USD')::int),2) pct_usd
     from pr p join cu c on c.customer_id=p.customer_id where c.country in ('Colombia','Argentina')
     group by 1,2 order by 1,2""")
print("== 1c. cliente con mezcla de monedas? (Colombia/Argentina)")
q("""with x as (select c.country, p.customer_id, count(distinct p.currency) k, count(*) np
     from pr p join cu c on c.customer_id=p.customer_id where c.country<>'México' group by 1,2)
     select country, k, count(*) nclientes, round(avg(np),2) prod_medios from x group by 1,2 order by 1,2""")

print("== 2. tx.currency por pais del cliente y consistencia con pr.currency")
q("""select c.country, t.currency, count(*) n from tx t join cu c on c.customer_id=t.customer_id group by 1,2 order by 1,2""")
q("""select count(*) n, round(100*avg((t.currency=p.currency)::int),3) pct_eq
     from tx t join pr p on p.product_id=t.product_id""")

print("== 3. amount_usd / amount por moneda (tabla completa)")
q("""select currency, count(*) n, round(100*avg((amount_usd is null)::int),2) pct_null,
       min(amount_usd/amount) rmin, max(amount_usd/amount) rmax, median(amount_usd/amount) rmed,
       stddev(amount_usd/amount)/avg(amount_usd/amount) cv
     from tx where amount<>0 group by 1 order by 1""")
q("""select currency, year(ts) y, count(amount_usd) n, round(median(amount_usd/amount),7) r,
       round(stddev(amount_usd/amount)/avg(amount_usd/amount),6) cv
     from tx where amount<>0 and amount_usd is not null group by 1,2 order by 1,2""")
q("""select currency,
       round(100*avg((abs(amount_usd - amount/4000) <= 0.006)::int),3) pct_eq_4000,
       round(100*avg((abs(amount_usd - amount/350) <= 0.006)::int),3) pct_eq_350,
       round(100*avg((abs(amount_usd - amount) <= 0.006)::int),3) pct_eq_1
     from tx where amount_usd is not null group by 1 order by 1""")

print("== 3b. fx diario vs constante")
q("""select src, dst, count(*) n, min(rate) mn, avg(rate) av, max(rate) mx, stddev(rate)/avg(rate) cv
     from fx where (src in ('COP','ARS') and dst='USD') or (src='USD' and dst in ('COP','ARS')) group by 1,2 order by 1,2""")
q("""with s as (select currency, amount, amount_usd, cast(ts as date) d from tx
               where amount_usd is not null and currency in ('COP','ARS'))
     select s.currency, count(*) n, count(f.rate) n_fx,
       round(100*avg((abs(s.amount_usd - s.amount*f.rate) <= 0.001*s.amount_usd + 0.01)::int),2) pct_match_rate_0p1,
       round(100*avg((abs(s.amount_usd - s.amount*f.rate) <= 0.01*s.amount_usd)::int),2) pct_match_rate_1pct,
       round(100*avg((abs(s.amount_usd - s.amount*f.rate) <= 0.005)::int),2) pct_match_cent,
       median(s.amount*f.rate/s.amount_usd) med_ratio_fx_vs_usd
     from s left join fx f on f.date=s.d and f.src=s.currency and f.dst='USD' group by 1 order by 1""")

print("== 4. cp.currency por pais")
q("""select c.country, cp.currency, count(*) n,
       round(100.0*count(*)/sum(count(*)) over (partition by c.country),2) pct
     from cp join cu c on c.customer_id=cp.customer_id group by 1,2 order by 1,2""")
q("""select round(100*avg((cp.currency = case c.country when 'México' then 'USD' when 'Colombia' then 'COP' when 'Argentina' then 'ARS' end)::int),2) pct_eq_ccy_pais_real,
            round(100*avg((cp.currency = case c.country when 'México' then 'MXN' when 'Colombia' then 'COP' when 'Argentina' then 'ARS' end)::int),2) pct_eq_ccy_pais_nominal,
            round(100*avg((exists(select 1 from pr p where p.customer_id=cp.customer_id and p.currency=cp.currency))::int),2) pct_in_prod_ccy,
            count(*) n
     from cp join cu c on c.customer_id=cp.customer_id where cp.currency is not null""")
q("""select c.country, round(100*avg((cp.currency = case c.country when 'Colombia' then 'COP' when 'Argentina' then 'ARS' else 'USD' end)::int),2) pct_eq
     from cp join cu c on c.customer_id=cp.customer_id where cp.currency is not null group by 1 order by 1""")

print("== 5. cp.claimed distribucion")
q("""select currency, count(*) n, count(claimed) n_claimed, min(claimed) mn, quantile_cont(claimed,0.25) q25,
       median(claimed) med, quantile_cont(claimed,0.75) q75, max(claimed) mx, avg(claimed) av
     from cp group by rollup(currency) order by 1""")
q("""select floor(claimed/500)::int b, count(*) n from cp where claimed is not null group by 1 order by 1""")
q("select t.currency, median(t.amount) med_tx, quantile_cont(t.amount,0.1) p10 from tx t group by 1 order by 1")

print("== 6. claimed ~ monto de alguna tx del mismo cliente (+-0.5%) vs placebo")
con.execute("create temp table c2 as select complaint_id, customer_id, claimed, currency, ts from cp where claimed is not null and claimed>0")
con.execute("""create temp table c2p as select c2.*, lead(customer_id) over (order by hash(complaint_id, 7)) other from c2""")
con.execute("create temp table tk as select customer_id, amount, amount_usd, currency, cast(ts as date) d from tx where customer_id in (select customer_id from c2 union select other from c2p)")
q("select count(*) n_c2, (select count(*) from tk) n_tx from c2")
q("""select count(*) n,
   round(100*avg((exists(select 1 from tk t where t.customer_id=c.customer_id and abs(t.amount-c.claimed)<=0.005*c.claimed))::int),3) own_amt,
   round(100*avg((exists(select 1 from tk t where t.customer_id=c.other and abs(t.amount-c.claimed)<=0.005*c.claimed))::int),3) placebo_amt,
   round(100*avg((exists(select 1 from tk t where t.customer_id=c.customer_id and abs(t.amount_usd-c.claimed)<=0.005*c.claimed))::int),3) own_usd,
   round(100*avg((exists(select 1 from tk t where t.customer_id=c.other and abs(t.amount_usd-c.claimed)<=0.005*c.claimed))::int),3) placebo_usd
   from c2p c where other is not null""")
# convertido con fx diario a la moneda del reclamo
q("""with h as (select c.complaint_id, bool_or(abs(t.amount*coalesce(f.rate,1) - c.claimed) <= 0.005*c.claimed) hit
       from c2 c join tk t on t.customer_id=c.customer_id
       left join fx f on f.date=t.d and f.src=t.currency and f.dst=c.currency and t.currency<>c.currency
       where c.currency is not null and (t.currency=c.currency or f.rate is not null)
       group by 1)
     select count(*) n_with_candidates, round(100*avg(hit::int),3) pct_hit_fx,
       round(100.0*sum(hit::int)/(select count(*) from c2 where currency is not null),3) pct_hit_over_all from h""")
