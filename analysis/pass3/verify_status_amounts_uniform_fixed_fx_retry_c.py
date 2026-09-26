"""Verificacion independiente (retry) de status_amounts_uniform_fixed_fx. Parte C: coincidencia con tasa diaria fx (datos completos)."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def show(sql, title=None):
    if title: print("==", title)
    cur = con.execute(sql); cols = [d[0] for d in cur.description]
    print(" | ".join(cols))
    for r in cur.fetchall(): print(" | ".join(str(round(v,5) if isinstance(v,float) else v) for v in r))
for datecol, lbl in [("cast(t.ts as date)", "fecha(ts)"), ("t.process_date", "process_date"), ("cast(t.ts as date) - interval 1 day", "fecha(ts)-1")]:
    show(f"""with t as (select currency, amount, amount_usd, ts, process_date from tx where amount_usd is not null),
    f1 as (select date, src, dst, rate, buy, sell from fx where src='USD'),
    f2 as (select date, src, dst, rate from fx where dst='USD')
    select t.currency, count(*) n, count(f1.rate) n_con_fx,
      round(100.0*avg(case when abs(t.amount/f1.rate - t.amount_usd) <= 0.005+1e-9 then 1 else 0 end),3) pct_rate_div,
      round(100.0*avg(case when abs(t.amount*f2.rate - t.amount_usd) <= 0.005+1e-9 then 1 else 0 end),3) pct_rate_inv_mult,
      round(100.0*avg(case when abs(t.amount/f1.buy - t.amount_usd) <= 0.005+1e-9 then 1 else 0 end),3) pct_buy,
      round(100.0*avg(case when abs(t.amount/f1.sell - t.amount_usd) <= 0.005+1e-9 then 1 else 0 end),3) pct_sell,
      round(100.0*avg(case when abs(t.amount/f1.rate - t.amount_usd) <= 0.01*t.amount_usd then 1 else 0 end),2) pct_rate_dentro_1pct,
      corr(t.amount/t.amount_usd, f1.rate) corr_ratio_rate_todos,
      corr(case when t.amount_usd>=10 then t.amount/t.amount_usd end, case when t.amount_usd>=10 then f1.rate end) corr_ratio_rate_usd10
    from t left join f1 on f1.date = {datecol} and f1.dst = t.currency
           left join f2 on f2.date = {datecol} and f2.src = t.currency
    group by 1 order by 1""", f"match con fx diaria usando {lbl}")
# referencia: mismo criterio con la tasa fija
show("""select currency, round(100.0*avg(case when abs(amount/(case currency when 'COP' then 4000 else 350 end) - amount_usd) <= 0.005+1e-9 then 1 else 0 end),3) pct_fija
 from tx where amount_usd is not null group by 1 order by 1""", "referencia tasa fija")
# las coincidencias con fx ¿son montos chicos o dias con tasa ~ fija?
show("""with t as (select currency, amount, amount_usd, cast(ts as date) d from tx where amount_usd is not null),
 f as (select date, dst, rate from fx where src='USD')
 select t.currency, count(*) n_match, round(median(t.amount_usd),2) med_usd, round(median(abs(f.rate/(case t.currency when 'COP' then 4000 else 350 end)-1))*100,4) med_desvio_tasa_pct
 from t join f on f.date=t.d and f.dst=t.currency where abs(t.amount/f.rate - t.amount_usd) <= 0.005+1e-9 group by 1 order by 1""", "perfil de coincidencias con fx")
