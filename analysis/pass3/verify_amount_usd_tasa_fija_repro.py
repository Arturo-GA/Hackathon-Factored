import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(title, s):
    print('==', title); print(con.execute(s).df().to_string(), '\n')

q('nulos por moneda', """select currency, count(*) n, sum((amount_usd is null)::int) nnull,
  round(100*avg((amount_usd is null)::int),3) pct_null from tx group by 1 order by 1""")
q('nulos global', "select round(100*avg((amount_usd is null)::int),3) pct_null from tx")

# cociente amount/amount_usd
q('cociente', """select currency, count(*) n, median(amount/amount_usd) med, avg(amount/amount_usd) mean,
  stddev(amount/amount_usd) sd, quantile_cont(amount/amount_usd,0.001) p001, quantile_cont(amount/amount_usd,0.999) p999
  from tx where amount_usd is not null and amount_usd<>0 group by 1""")
# USD non-null? (none expected)
q('cociente por año', """select currency, year(ts) y, count(*) n, median(amount/amount_usd) med, stddev(amount/amount_usd) sd
  from tx where amount_usd is not null and amount_usd<>0 group by 1,2 order by 1,2""")

# regla exacta
q('regla exacta', """with t as (select currency, amount, amount_usd, case currency when 'ARS' then 350.0 when 'COP' then 4000.0 end K
  from tx where amount_usd is not null)
  select currency, count(*) n,
   sum((amount_usd = round(amount/K,2))::int) n_exact,
   round(100*avg((amount_usd = round(amount/K,2))::int),4) pct_exact,
   round(100*avg((abs(amount_usd - amount/K) <= 0.005 + 1e-9)::int),4) pct_le_0005,
   max(abs(amount_usd - amount/K)) maxdiff,
   max(abs(amount_usd - round(amount/K,2))) maxdiff_round
  from t group by 1""")
# where not exact: what is diff?
q('no exactas detalle', """with t as (select currency, amount, amount_usd, case currency when 'ARS' then 350.0 when 'COP' then 4000.0 end K
  from tx where amount_usd is not null)
  select currency, count(*) n, min(amount_usd - round(amount/K,2)) mn, max(amount_usd - round(amount/K,2)) mx,
   median(amount) med_amt from t where amount_usd <> round(amount/K,2) group by 1""")
q('ejemplos no exactas', """with t as (select currency, amount, amount_usd, case currency when 'ARS' then 350.0 when 'COP' then 4000.0 end K
  from tx where amount_usd is not null)
  select currency, amount, amount_usd, amount/K raw, round(amount/K,2) r from t where amount_usd <> round(amount/K,2) limit 8""")

# fx
q('fx pares', "select src,dst,count(*) n, min(rate) mn, max(rate) mx, avg(rate) av, min(date) d0, max(date) d1 from fx group by 1,2 order by 1,2")

# comparacion con fx del dia (USD->X), fecha ts
for c in ['ARS','COP']:
    K = 350.0 if c=='ARS' else 4000.0
    q(f'fx vs {c} (fecha ts, USD->{c})', f"""with t as (select cast(ts as date) d, amount, amount_usd, amount/amount_usd ratio from tx
       where currency='{c}' and amount_usd is not null and amount_usd>0.5),
      f as (select date, rate, buy, sell from fx where src='USD' and dst='{c}')
      select count(*) n, corr(t.ratio, f.rate) corr_ratio_rate,
        median(abs(t.amount/f.rate - t.amount_usd)/t.amount_usd) mre_rate,
        median(abs(t.amount/f.buy - t.amount_usd)/t.amount_usd) mre_buy,
        median(abs(t.amount/f.sell - t.amount_usd)/t.amount_usd) mre_sell,
        median(abs(t.amount/{K} - t.amount_usd)/t.amount_usd) mre_K,
        avg(f.rate) avg_fx, stddev(f.rate) sd_fx, min(f.rate) mn_fx, max(f.rate) mx_fx
      from t join f on t.d=f.date""")
    q(f'fx vs {c} (process_date, X->USD inverso)', f"""with t as (select process_date d, amount, amount_usd from tx
       where currency='{c}' and amount_usd is not null and amount_usd>0.5),
      f as (select date, rate from fx where src='{c}' and dst='USD')
      select count(*) n, median(abs(t.amount*f.rate - t.amount_usd)/t.amount_usd) mre_inv
      from t join f on t.d=f.date""")

# independencia de nulos (ARS/COP)
for col, expr in [('fraud','fraud'),('status','status'),('channel','channel'),('trimestre',"strftime(ts,'%Y-Q')||quarter(ts)"),
                  ('fscore_null','fscore is null'),('lat_null','lat is null'),('merchant_null','merchant_name is null'),('ttype','ttype')]:
    q(f'nulos vs {col}', f"""select {expr} g, count(*) n, round(100*avg((amount_usd is null)::int),3) pct_null
      from tx where currency<>'USD' group by 1 order by 1""")

# varianza por cliente de la tasa de nulos vs binomial
q('varianza por cliente', """with c as (select customer_id, count(*) n, avg((amount_usd is null)::double) r from tx where currency<>'USD' group by 1 having count(*)>=5),
  p as (select avg((amount_usd is null)::double) p from tx where currency<>'USD')
  select count(*) nclientes, var_pop(r) var_obs, avg(p.p*(1-p.p)/n) var_esperada from c, p""")

# productos por pais de cliente y moneda
q('productos pais x moneda', """select cu.country, pr.currency, count(*) n from pr join cu using(customer_id) group by 1,2 order by 1,2""")
q('tx pais cliente x moneda', """select cu.country, tx.currency, count(*) n from tx join cu using(customer_id) group by 1,2 order by 1,2""")

# no exactas: ¿son todas empates de medio centavo?
q('no exactas = empates', """with t as (select currency, amount, amount_usd, case currency when 'ARS' then 350.0 when 'COP' then 4000.0 end K
  from tx where amount_usd is not null)
  select currency, count(*) n_noexact, sum((abs(amount/K*100 - floor(amount/K*100) - 0.5) < 1e-6)::int) n_tie
  from t where amount_usd <> round(amount/K,2) group by 1""")
q('empates totales', """with t as (select currency, amount, amount_usd, case currency when 'ARS' then 350.0 when 'COP' then 4000.0 end K
  from tx where amount_usd is not null)
  select currency, sum((abs(amount/K*100 - floor(amount/K*100) - 0.5) < 1e-6)::int) n_tie,
   sum(((abs(amount/K*100 - floor(amount/K*100) - 0.5) < 1e-6) and amount_usd = round(amount/K,2))::int) tie_up
  from t group by 1""")
