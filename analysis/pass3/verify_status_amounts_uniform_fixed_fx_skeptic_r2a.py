# Verificador escéptico r2a: esquema, nulos de amount_usd, tasa fija vs tabla fx (con desfases de fecha y buy/sell)
import duckdb, time, pandas as pd
t0 = time.time()
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
def q(s):
    print(con.execute(s).df().to_string(), '\n', flush=True)

print("== 0. tipos de columnas ==")
q("select column_name, data_type from information_schema.columns where table_name in ('tx','fx') and column_name in ('amount','amount_usd','currency','ts','process_date','date','rate','buy','sell','src','dst','source','code')")

print("== 1. nulos de amount_usd por moneda ==")
q("""select currency, count(*) n, count(amount_usd) no_nulos, round(100*avg((amount_usd is null)::int),3) pct_nulo
     from tx group by 1 order by 1""")
q("select count(*) n, round(100*avg((amount_usd is null)::int),3) pct_nulo_total from tx")

print("== 2. pais del cliente x moneda de la tx ==")
q("""select c.country, t.currency, count(*) n from tx t join cu c using(customer_id) group by all order by all""")

print("== 3. tasa fija: diferencia exacta (redondeo a centavos) ==")
q("""with t as (select currency, amount, amount_usd, amount/(case currency when 'COP' then 4000.0 when 'ARS' then 350.0 end) raw
      from tx where amount_usd is not null)
     select currency, count(*) n,
       sum((abs(amount_usd - round(raw,2)) < 1e-9)::int) igual_round2,
       sum((abs(amount_usd - raw) <= 0.005 + 1e-9)::int) dentro_medio_centavo,
       sum((abs(amount_usd - floor(raw*100)/100) < 1e-9)::int) igual_trunc,
       max(abs(amount_usd - raw)) max_absdiff,
       min(amount_usd) min_usd, max(amount_usd) max_usd,
       sum((round(amount_usd,2) <> amount_usd)::int) usd_no_2dec
     from t group by 1 order by 1""")

print("== 4. tabla fx: pares, niveles y rango de fechas ==")
q("""select src, dst, count(*) n, count(distinct date) dias, min(date) d0, max(date) d1,
     round(min(rate),4) mn, round(avg(rate),4) av, round(max(rate),4) mx, round(stddev(rate)/avg(rate)*100,3) cv_pct,
     count(distinct source) nsrc
     from fx group by 1,2 order by 1,2""")
q("select source, count(*) from fx group by 1 order by 2 desc limit 5")

print("== 5. ¿alguna tasa diaria (rate/buy/sell, directa o inversa, desfase -3..+3 dias) reproduce amount_usd? ==")
rows = []
for cur in ['COP', 'ARS']:
    for shift in [-3, -2, -1, 0, 1, 2, 3]:
        r = con.execute(f"""
        with f as (select date, rate, buy, sell from fx where src='USD' and dst='{cur}'),
             g as (select date, rate irate from fx where src='{cur}' and dst='USD'),
             t as (select amount, amount_usd, cast(ts as date) + {shift} d from tx
                   where currency='{cur}' and amount_usd >= 100)
        select count(*) n, count(f.rate) con_fx,
          sum((abs(t.amount_usd - round(t.amount/f.rate,2)) <= 0.0051)::int) m_rate,
          sum((abs(t.amount_usd - round(t.amount/f.buy,2)) <= 0.0051)::int) m_buy,
          sum((abs(t.amount_usd - round(t.amount/f.sell,2)) <= 0.0051)::int) m_sell,
          sum((abs(t.amount_usd - round(t.amount*g.irate,2)) <= 0.0051)::int) m_inv,
          corr(t.amount/t.amount_usd, f.rate) corr_ratio_rate,
          stddev(t.amount/t.amount_usd) sd_ratio
        from t left join f on f.date=t.d left join g on g.date=t.d""").fetchone()
        rows.append((cur, shift) + tuple(r))
print(pd.DataFrame(rows, columns=['cur','shift','n','con_fx','m_rate','m_buy','m_sell','m_inv','corr','sd_ratio']).to_string(), '\n')
# process_date
for cur in ['COP','ARS']:
    q(f"""with f as (select date, rate from fx where src='USD' and dst='{cur}')
    select '{cur}' cur, count(*) n, sum((abs(t.amount_usd - round(t.amount/f.rate,2)) <= 0.0051)::int) m_procdate
    from tx t join f on f.date=t.process_date where t.currency='{cur}' and t.amount_usd >= 100""")
print(f"[t={time.time()-t0:.0f}s]")

print("== 6. coincidencias con fx: ¿azar? (por monto y distancia de la tasa a K) ==")
for cur, K in [('COP', 4000.0), ('ARS', 350.0)]:
    q(f"""with f as (select date, rate from fx where src='USD' and dst='{cur}'),
    t as (select amount, amount_usd, cast(ts as date) d from tx where currency='{cur}' and amount_usd is not null)
    select case when t.amount_usd < 10 then 'a<10' when t.amount_usd < 100 then 'b10-100' when t.amount_usd < 1000 then 'c100-1k' else 'd>=1k' end bucket,
      count(*) n, round(100*avg((abs(t.amount_usd - round(t.amount/f.rate,2)) <= 0.0051)::int),3) pct_match_fx,
      round(100*avg(abs(f.rate/{K}-1)),3) mean_abs_dev_pct
    from t join f on f.date=t.d group by 1 order by 1""")
print(f"[t={time.time()-t0:.0f}s]")
