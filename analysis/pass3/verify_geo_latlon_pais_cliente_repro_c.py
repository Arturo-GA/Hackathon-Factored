import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('==',t), print(con.execute(s).df().to_string(), '\n'))
# own-country raw rows: city mismatch (would reveal foreign-branch picks of own country)
q('own-country raw rows city mismatch', """select cu.country cc, t.country_raw, count(*) n, count(t.city) n_city, sum((t.city<>cu.city)::int) n_city_mismatch
  from tx t join cu using(customer_id) where t.country=cu.country group by all order by 1,2""")
# branch analysis
q('branch join coverage', """select t.channel, count(*) n_with_branch, count(b.branch_id) n_found from tx t left join br b on b.branch_id=t.branch_id where t.branch_id is not null group by 1""")
q('branch country vs customer / tx country', """select (t.country<>cu.country) foreign_, count(*) n, avg((b.country=cu.country)::int) br_eq_cust, avg((b.country=t.country)::int) br_eq_tx
  from tx t join cu using(customer_id) join br b on b.branch_id=t.branch_id group by all""")
q('branch same city as customer vs 1/ncities', """with nc as (select country, count(distinct city) ncity, count(*) nbr from br group by 1)
  select b.country, count(*) n, avg((b.city=cu.city)::int) same_city, 1.0/any_value(nc.ncity) inv_ncity, any_value(nc.nbr) nbr,
  avg((b.city=t.city)::int) br_city_eq_txcity
  from tx t join cu using(customer_id) join br b on b.branch_id=t.branch_id join nc on nc.country=b.country group by 1""")
# customer city in branch city list?
q('customer cities vs branch cities', """select cu.country, count(distinct cu.city) n_cust_cities, count(distinct cu.city) filter (where cu.city in (select city from br)) in_br from cu group by 1""")
# uniformity of branch pick within country: branch usage counts dispersion
q('branch usage dispersion', """with u as (select b.country, t.branch_id, count(*) n from tx t join br b using(branch_id) group by all)
  select country, count(*) nbr_used, avg(n) mean_n, stddev(n) sd_n, min(n), max(n) from u group by 1""")
q('br zero coords', """select count(*) n, sum((lat=0 and lon=0)::int) exact_zero, sum((abs(lat)<1 and abs(lon)<1)::int) near_zero,
  string_agg(distinct case when abs(lat)<1 and abs(lon)<1 then city||'('||country||')' end, ', ') cities_zero from br""")
q('br zero by country', "select country, count(*) n, sum((abs(lat)<1 and abs(lon)<1)::int) near_zero, count(distinct city) ncity from br group by 1")
q('br city coords nonzero sample', "select city, country, count(*) n, min(lat), max(lat), min(lon), max(lon) from br where not (abs(lat)<1 and abs(lon)<1) group by all order by 2,1")
q('br near-zero ranges', "select country, city, count(*) n, min(lat), max(lat), min(lon), max(lon) from br where abs(lat)<1 and abs(lon)<1 group by all order by 1,2")
q('foreign-branch per-option rate', """select cu.country cc, count(*) n,
  sum((t.country_raw in ('USA','Spain','Brazil','Mexico') or t.country<>cu.country)::int) n_foreign_branch,
  count(distinct case when t.country_raw in ('USA','Spain','Brazil','Mexico') or t.country<>cu.country then t.country_raw end) n_options
  from tx t join cu using(customer_id) group by 1""")
