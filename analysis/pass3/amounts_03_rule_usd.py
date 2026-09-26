import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
# exact rule: amount_usd == round(amount / K, 2)
q("""select currency, count(*) n,
 avg((amount_usd = round(amount/(case currency when 'ARS' then 350 when 'COP' then 4000 end),2))::int) exact_round,
 avg((abs(amount_usd - amount/(case currency when 'ARS' then 350 when 'COP' then 4000 end))<=0.0051)::int) within_half_cent,
 max(abs(amount_usd - amount/(case currency when 'ARS' then 350 when 'COP' then 4000 end))) maxdiff
 from tx where amount_usd is not null group by all""")
# inverse: amount == round(amount_usd*K,2)?
q("""select currency, avg((round(amount_usd*(case currency when 'ARS' then 350 when 'COP' then 4000 end),2)=amount)::int) inv_exact from tx where amount_usd is not null group by all""")
# null amount_usd in ARS/COP: random? by status/fraud/ttype/year
q("""select currency, fraud, count(*) n, avg((amount_usd is null)::int) nul from tx where currency<>'USD' group by all order by 1,2""")
q("""select currency, (fscore is null) fs_null, count(*) n, avg((amount_usd is null)::int) nul from tx where currency<>'USD' group by all order by 1,2""")
q("""select currency, (lat is null) lat_null, count(*) n, avg((amount_usd is null)::int) nul from tx where currency<>'USD' group by all order by 1,2""")
q("""select currency, (merchant_name is null) mn_null, (tcat is null) tc_null, count(*) n, avg((amount_usd is null)::int) nul from tx where currency<>'USD' group by all order by 1,2,3""")
# fx internal consistency
q("""select a.src,a.dst, avg(a.rate*b.rate) prod_inv, stddev(a.rate*b.rate) sd, min(a.rate*b.rate) mn, max(a.rate*b.rate) mx
 from fx a join fx b on a.date=b.date and a.src=b.dst and a.dst=b.src where a.src<b.src group by all""")
q("""select avg((buy<rate and rate<sell)::int) ordered, avg((sell-buy)/rate) spread, min((sell-buy)/rate), max((sell-buy)/rate) from fx""")
# triangular: USD->ARS vs USD->MXN * MXN->ARS
q("""select avg(ua.rate/(um.rate*ma.rate)) tri, stddev(ua.rate/(um.rate*ma.rate)) sd from fx ua join fx um on ua.date=um.date and um.src='USD' and um.dst='MXN'
 join fx ma on ma.date=ua.date and ma.src='MXN' and ma.dst='ARS' where ua.src='USD' and ua.dst='ARS'""")
# fx autocorrelation (random walk vs iid)
q("""with u as (select date, rate, lag(rate) over (order by date) pr from fx where src='USD' and dst='ARS') select corr(rate,pr) ac1, stddev(rate/pr-1) sd_ret from u""")
q("""select source, count(*) from fx group by all""")
