import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(title, s):
    print('==', title); print(con.execute(s).df().to_string(), '\n')

q('tipos', "select column_name, data_type from information_schema.columns where table_name='pr' and column_name in ('opened','expires','bal','credit_limit','currency','ptype')")
q('pr por ptype', """select ptype, currency, count(*) n, min(bal) minbal, avg((bal<0)::int) neg, avg((credit_limit is not null)::int) has_lim from pr group by all order by 1,2""")

# 1. tx antes de apertura / despues vencimiento
q('antes apertura total', """select count(*) n, sum((t.ts::date < p.opened)::int) before_open, avg((t.ts::date < p.opened)::int) sh_before,
   sum((p.expires is not null and t.ts::date > p.expires)::int) after_exp,
   sum((p.product_id is null)::int) no_prod
   from tx t left join pr p using(product_id)""")
q('antes apertura por anio apertura', """select year(p.opened) y, count(*) n, avg((t.ts::date < p.opened)::int) sh_before,
   median(date_diff('day', t.ts::date, p.opened)) filter (where t.ts::date < p.opened) med_days
   from tx t join pr p using(product_id) group by 1 order by 1""")
q('mediana global dias antes', """select median(date_diff('day', t.ts::date, p.opened)) med from tx t join pr p using(product_id) where t.ts::date < p.opened""")
# uniformidad temporal: tx por semestre segun cohorte de apertura (share dentro de cohorte)
q('distribucion temporal por cohorte (share por anio de tx)', """with a as (select year(p.opened) oy, year(t.ts) ty, count(*) n from tx t join pr p using(product_id) group by all)
   select oy, ty, n, round(n/sum(n) over (partition by oy),4) sh from a where oy>=2023 order by oy, ty""")
q('rango tx', "select min(ts), max(ts) from tx")

# 2. rechazo antes/despues apertura
q('rechazo vs antes apertura', """select (t.ts::date < p.opened) before_open, count(*) n, avg((t.status='Declined')::int) decl,
   avg((t.code='51')::int) c51, avg((t.code='54')::int) c54, avg(t.fraud::int)*1000 fraud_pm
   from tx t join pr p using(product_id) group by 1""")
# 3. vencimiento
q('tras vencimiento', """select (t.ts::date > p.expires) after_exp, count(*) n, avg((t.status='Declined')::int) decl, avg((t.code='54')::int) c54, avg((t.code='51')::int) c51
   from tx t join pr p using(product_id) where p.expires is not null group by 1""")
q('vencimiento por ptype', """select p.ptype, count(*) n, sum((t.ts::date > p.expires)::int) after_exp from tx t join pr p using(product_id) where p.expires is not null group by 1""")

# 4. saldo vs flujo neto aprobado (en moneda local, misma moneda que producto)
q('corr bal vs flujo neto', """with f as (select product_id,
     sum(case when ttype='Deposit' then amount when ttype in ('Withdrawal','Purchase','Payment','Transfer') then -amount else 0 end) net,
     sum(amount) gross, count(*) n from tx where status='Approved' group by 1)
   select p.ptype, p.currency, count(*) np, corr(f.net, p.bal) r_net, corr(f.gross, p.bal) r_gross, corr(f.n, p.bal) r_n,
     avg(f.net) mean_net_local, min(p.bal) minbal from f join pr p using(product_id) group by all order by 1,2""")
q('corr bal vs flujo neto (USD-eq, pooled ptype)', """with f as (select product_id,
     sum(case when ttype='Deposit' then 1 when ttype in ('Withdrawal','Purchase','Payment','Transfer') then -1 else 0 end *
         amount/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)) net from tx where status='Approved' group by 1)
   select p.ptype, count(*) np, corr(f.net, p.bal/(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)) r,
     avg(f.net) mean_net_usd, avg(p.bal/(case p.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)) mean_bal_usd,
     avg((f.net<0)::int) share_net_neg from f join pr p using(product_id) group by 1 order by 2 desc""")

# 5. Tarjeta credito bal > limite
q('TC bal>limite (productos)', """select count(*) n, avg((bal>credit_limit)::int) sh from pr where ptype='Tarjeta Crédito'""")
q('TC bal>limite (tx)', """select (p.bal>p.credit_limit) over_lim, count(*) n, avg((t.status='Declined')::int) decl, avg((t.code='51')::int) c51
   from tx t join pr p using(product_id) where p.ptype='Tarjeta Crédito' group by 1""")
q('TC monto > disponible', """select (t.amount > p.credit_limit - p.bal) over_avail, count(*) n, avg((t.status='Declined')::int) decl, avg((t.code='51')::int) c51
   from tx t join pr p using(product_id) where p.ptype='Tarjeta Crédito' and t.ttype in ('Purchase','Withdrawal') group by 1""")
q('monto > saldo en debito/ahorro/corriente', """select (t.amount > p.bal) over_bal, count(*) n, avg((t.status='Declined')::int) decl, avg((t.code='51')::int) c51
   from tx t join pr p using(product_id) where p.ptype in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Débito') and t.ttype in ('Withdrawal','Purchase','Transfer') group by 1""")
q('monto > saldo por ptype', """select p.ptype, (t.amount > p.bal) over_bal, count(*) n, avg((t.status='Declined')::int) decl, avg((t.code='51')::int) c51
   from tx t join pr p using(product_id) where p.ptype in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Débito') and t.ttype in ('Withdrawal','Purchase','Transfer') group by 1,2 order by 1,2""")
# decline por decil de ratio monto/saldo (dosis-respuesta)
q('decline por decil amount/bal (debito/ahorro)', """with x as (select t.status, t.code, t.amount/nullif(p.bal,0) r from tx t join pr p using(product_id)
    where p.ptype in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Débito') and t.ttype in ('Withdrawal','Purchase','Transfer') and p.bal>0)
   select ntile(10) over (order by r) d, r, status, code from x""") if False else None
q('decline por decil amount/bal', """with x as (select t.status, t.code, t.amount/nullif(p.bal,0) r from tx t join pr p using(product_id)
    where p.ptype in ('Cuenta Ahorro','Cuenta Corriente','Tarjeta Débito') and t.ttype in ('Withdrawal','Purchase','Transfer') and p.bal>0),
   y as (select *, ntile(10) over (order by r) d from x)
   select d, count(*) n, min(r) rmin, max(r) rmax, avg((status='Declined')::int) decl, avg((code='51')::int) c51 from y group by 1 order by 1""")
# pstatus: tx solo en Active? y last_tx vs max tx
q('last_tx vs max ts', """with m as (select product_id, max(ts)::date mx, min(ts)::date mn from tx group by 1)
   select count(*) n, avg((p.last_tx::date = m.mx)::int) eq_last, avg((p.last_tx::date < m.mx)::int) last_before_max, avg((p.opened <= m.mn)::int) opened_before_first
   from m join pr p using(product_id)""")
