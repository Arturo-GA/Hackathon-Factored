# Parte E: (1) K fijo vs tipo de cambio diario; (2) R2 teórico de log(monto)|ttype; (3) ¿montos de tx enlazados con cp.claimed o de.event_value? (vs línea base desplazada)
import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
K="(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)"
print('== 1) fx USD->ARS/COP en la tabla fx vs K fijo ==')
q("select src, dst, min(rate) mn, median(rate) med, max(rate) mx, min(date) d0, max(date) d1 from fx where src='USD' and dst in ('ARS','COP','MXN') group by all")
q(f"""select t.currency, count(*) n, corr(t.amount, f.rate) r_amount_vs_dailyfx, corr(t.amount/{K.replace('currency','t.currency')}, f.rate) r_usdeq_vs_dailyfx,
 max(abs(t.amount_usd - round(t.amount/{K.replace('currency','t.currency')},2))) max_err_amount_usd_fixedK
 from tx t join fx f on f.date=cast(t.ts as date) and f.src='USD' and f.dst=t.currency where t.ttype in ('Transfer','Deposit') group by all""")
print('== 2) R2 de log(monto USD-eq) explicado por ttype (ANOVA exacto en datos completos) ==')
q(f"""with b as (select ttype, ln(amount/{K}) la from tx), t as (select ttype, count(*) n, var_pop(la) v from b group by 1)
 select 1 - (select sum(n*v) from t)/((select count(*) from b)*(select var_pop(la) from b)) r2_log_ttype""")
q(f"""with b as (select ttype, amount/{K} a from tx), t as (select ttype, count(*) n, var_pop(a) v from b group by 1)
 select 1 - (select sum(n*v) from t)/((select count(*) from b)*(select var_pop(a) from b)) r2_lineal_ttype""")
print('== 3a) cp.claimed: ¿coincide con algún monto de tx del mismo cliente? vs línea base (cliente desplazado) ==')
q("select currency, count(*) n, avg((claimed is null)::int) nul, min(claimed) mn, median(claimed) med, max(claimed) mx from cp group by all")
q("""with c as (select complaint_id, customer_id, claimed, currency, ts from cp where claimed is not null),
 cs as (select complaint_id, lead(customer_id) over (order by complaint_id) customer_id, claimed, currency, ts from c)
 select 'mismo_cliente' k, count(distinct c.complaint_id) n_match from c join tx t on t.customer_id=c.customer_id and t.currency=c.currency and abs(t.amount-c.claimed)<0.005
 union all
 select 'cliente_desplazado', count(distinct cs.complaint_id) from cs join tx t on t.customer_id=cs.customer_id and t.currency=cs.currency and abs(t.amount-cs.claimed)<0.005""")
print('== 3b) de.event_value (Purchase/FormSubmit) vs montos USD-eq del mismo cliente ±1 día, vs línea base (evento desplazado 30 días) ==')
con.execute("create temp table e as select event_id, customer_id, event_value v, ts from de where event_value is not null and customer_id is not null using sample 40000 rows")
q(f"""select 'mismo_dia' k, count(distinct e.event_id) n_match, (select count(*) from e) n_ev from e join tx t on t.customer_id=e.customer_id
   and t.ts between e.ts - interval 1 day and e.ts + interval 1 day and abs(t.amount/(case t.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) - e.v) < 0.01
 union all
 select 'desplazado_30d', count(distinct e.event_id), (select count(*) from e) from e join tx t on t.customer_id=e.customer_id
   and t.ts between e.ts + interval 29 day and e.ts + interval 31 day and abs(t.amount/(case t.currency when 'ARS' then 350 when 'COP' then 4000 else 1 end) - e.v) < 0.01""")
