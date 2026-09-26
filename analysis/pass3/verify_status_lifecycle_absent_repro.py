"""Verificacion independiente: status_lifecycle_absent (gemelas, Pending envejecidas, duplicados)."""
import duckdb, time, sys
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
t0 = time.time()
step = sys.argv[1] if len(sys.argv) > 1 else 'all'
def T(): return f"[{time.time()-t0:.0f}s]"

if step in ('all', 'base'):
    print("== rango y estados ==")
    print(q("select min(ts) mn, max(ts) mx, count(*) n from tx").to_string())
    print(q("select status, count(*) n, round(100*count(*)/sum(count(*)) over (),3) pct, min(amount) amin, sum(case when amount<=0 then 1 else 0 end) n_nonpos from tx group by 1 order by 2 desc").to_string())
    # unicidad del par (producto, monto): fraccion de filas cuyo par aparece >1 vez
    print(q("""select count(*) grupos, sum(case when c>1 then 1 else 0 end) grupos_rep, sum(case when c>1 then c else 0 end) filas_rep,
      round(100.0*sum(case when c>1 then 1 else 0 end)/count(*),4) pct_grupos_rep
      from (select product_id, amount, count(*) c from tx group by 1,2)""").to_string(), T())

if step in ('all', 'twin'):
    print("== gemela exacta (mismo producto + mismo monto, cualquier otra tx) por estado ==")
    print(q("""with p as (select product_id, amount, count(*) c from tx group by 1,2)
      select t.status, count(*) n, sum(case when p.c>1 then 1 else 0 end) con_gemela,
        round(100.0*sum(case when p.c>1 then 1 else 0 end)/count(*),4) pct
      from tx t join p using(product_id, amount) group by 1 order by 1""").to_string(), T())
    print("== gemela exacta de monto negativo/opuesto (producto, -monto) ==")
    print(q("""select count(*) from tx a join tx b on a.product_id=b.product_id and b.amount=-a.amount where a.status='Reversed'""").to_string(), T())

if step in ('all', 'approx'):
    print("== gemela aproximada: mismo cliente, monto +-1%, +-24h (por estado, incluye Approved como baseline) ==")
    print(q("""with s as (select transaction_id, customer_id, amount, ts, status from tx)
      select s.status, count(distinct s.transaction_id) n_con_gemela
      from s join tx t on t.customer_id=s.customer_id and t.transaction_id<>s.transaction_id
       and t.ts between s.ts - interval 1 day and s.ts + interval 1 day
       and abs(t.amount - s.amount) <= 0.01*abs(s.amount)
      group by 1 order by 1""").to_string(), T())

if step in ('all', 'pending'):
    print("== Pending: antiguedad y tasa por anio / ultimos dias ==")
    print(q("""select year(ts) y, count(*) n, round(100*avg(case when status='Pending' then 1 else 0 end),3) pend_pct,
      round(100*avg(case when status='Reversed' then 1 else 0 end),3) rev_pct,
      round(100*avg(case when status='Declined' then 1 else 0 end),3) dec_pct from tx group by 1 order by 1""").to_string())
    print(q("""with m as (select max(ts) mx from tx)
      select case when date_diff('day', ts, mx) <= 7 then 'a_<=7d' when date_diff('day', ts, mx) <= 30 then 'b_8-30d'
        when date_diff('day', ts, mx) <= 90 then 'c_31-90d' else 'd_>90d' end edad,
        count(*) n, sum(case when status='Pending' then 1 else 0 end) n_pend,
        round(100*avg(case when status='Pending' then 1 else 0 end),3) pend_pct
      from tx, m group by 1 order by 1""").to_string())
    print(q("""with m as (select max(ts) mx from tx)
      select count(*) n_pend, round(100*avg(case when date_diff('day', ts, mx) > 30 then 1 else 0 end),2) pct_mas_30d,
        round(100*avg(case when date_diff('day', ts, mx) > 7 then 1 else 0 end),2) pct_mas_7d
      from tx, m where status='Pending'""").to_string())
    print(q("""with m as (select max(ts) mx from tx)
      select round(100*avg(case when date_diff('day', ts, mx) > 30 then 1 else 0 end),2) pct_todas_mas_30d from tx, m""").to_string())
    # process_date vs ts por estado
    print(q("""select status, round(avg(date_diff('day', cast(ts as date), process_date)),3) lag_med, min(date_diff('day', cast(ts as date), process_date)) mn,
      max(date_diff('day', cast(ts as date), process_date)) mx, round(100*avg(case when process_date is null then 1 else 0 end),2) pd_null from tx group by 1""").to_string(), T())

if step in ('all', 'dup'):
    print("== mismo cliente + mismo comercio: pares consecutivos ==")
    print(q("""with w as (select customer_id, merchant_name, ts, amount,
       lead(ts) over (partition by customer_id, merchant_name order by ts) nts,
       lead(amount) over (partition by customer_id, merchant_name order by ts) namt
       from tx where merchant_name is not null)
      select count(*) filas, count(nts) pares,
       sum(case when date_diff('second',ts,nts)<=600 then 1 else 0 end) le10m,
       sum(case when date_diff('second',ts,nts)<=3600 then 1 else 0 end) le1h,
       sum(case when date_diff('second',ts,nts)<=86400 then 1 else 0 end) le24h,
       sum(case when date_diff('second',ts,nts)<=86400 and abs(namt-amount)<=0.01*amount then 1 else 0 end) le24h_monto1pct,
       sum(case when namt=amount then 1 else 0 end) mismo_monto_exacto_cualquier_gap
      from w""").to_string(), T())
    print("== mismo cliente (cualquier comercio): pares consecutivos y expectativa uniforme ==")
    print(q("""with w as (select customer_id, ts, lead(ts) over (partition by customer_id order by ts) nts from tx)
      select count(nts) pares, sum(case when date_diff('second',ts,nts)<=600 then 1 else 0 end) le10m,
       sum(case when date_diff('second',ts,nts)<=3600 then 1 else 0 end) le1h,
       sum(case when date_diff('second',ts,nts)=0 then 1 else 0 end) gap0,
       median(date_diff('hour',ts,nts)) med_gap_h from w""").to_string(), T())
    # expectativa si las tx de cada cliente fueran uniformes en su ventana [min,max]
    print(q("""with c as (select customer_id, count(*) n, date_diff('second', min(ts), max(ts)) span from tx group by 1 having count(*)>1)
      select sum((n-1) * (1 - pow(1 - least(600.0/nullif(span,0),1), n))) exp_le10m_aprox,
             sum((n-1) * (600.0/nullif(span,0)) * n) exp_le10m_naive from c""").to_string(), T())
    print("== colisiones de timestamp ==")
    print(q("select count(*) grupos, sum(c) filas from (select customer_id, ts, count(*) c from tx group by 1,2 having count(*)>1)").to_string())
    print(q("select count(*) grupos, sum(c) filas from (select product_id, ts, count(*) c from tx group by 1,2 having count(*)>1)").to_string(), T())

if step in ('all', 'expm'):
    print("== expectativa uniforme para mismo cliente+comercio ==")
    print(q("""with c as (select customer_id, merchant_name, count(*) n, date_diff('second', min(ts), max(ts)) span
               from tx where merchant_name is not null group by 1,2 having count(*)>1)
      select count(*) grupos, sum(n-1) pares, sum((n-1)*n*600.0/nullif(span,0)) exp_le10m, sum((n-1)*n*3600.0/nullif(span,0)) exp_le1h,
             sum((n-1)*n*86400.0/nullif(span,0)) exp_le24h from c""").to_string(), T())
    # expectativa con span global (3 anios) en vez del span de cada grupo (el span del grupo sesga hacia arriba con n=2)
    print(q("""with c as (select customer_id, merchant_name, count(*) n from tx where merchant_name is not null group by 1,2 having count(*)>1)
      select sum((n-1)*n*600.0/(1096*86400)) exp_le10m, sum((n-1)*n*3600.0/(1096*86400)) exp_le1h, sum((n-1)*n*86400.0/(1096*86400)) exp_le24h from c""").to_string(), T())
