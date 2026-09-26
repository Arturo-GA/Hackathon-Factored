import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('==',t), print(con.execute(s).df().to_string(), '\n'))
q('country_raw x customer country', "pivot (select t.country_raw, cu.country cc from tx t join cu using(customer_id)) on cc using count(*) group by country_raw order by country_raw")
q('n tx by customer country + foreign count', """select cu.country cc, count(*) n, sum((t.country<>cu.country)::int) n_foreign, avg((t.country<>cu.country)::int) foreign_rate,
  sum((t.country_raw not in ('México','Colombia','Argentina'))::int) n_raw_offlist from tx t join cu using(customer_id) group by 1""")
q('total foreign', "select count(*) n, sum((t.country<>cu.country)::int) n_foreign from tx t join cu using(customer_id)")
# city: domestic vs foreign; does foreign have city? and for 'Mexico' raw rows of MX customers, city = customer city?
q('city by raw branch', """select case when t.country_raw in ('USA','Spain','Brazil','Mexico') then t.country_raw else 'home/latam_raw' end grp,
   (t.country<>cu.country) foreign_, count(*) n, avg((t.city is null)::int) city_null, avg((t.city=cu.city)::int) same_city_as_cust
   from tx t join cu using(customer_id) group by all order by 1,2""")
q('cities appearing in foreign tx (top)', """select t.country, t.city, count(*) n from tx t join cu using(customer_id) where t.country<>cu.country group by all order by 3 desc limit 15""")
q('foreign rate by channel', "select t.channel, count(*) n, avg((t.country<>cu.country)::int) fr, avg((t.country_raw in ('USA','Spain','Brazil','Mexico'))::int) raw_foreignish from tx t join cu using(customer_id) group by 1 order by 1")
q('foreign rate by ttype', "select t.ttype, count(*) n, avg((t.country<>cu.country)::int) fr from tx t join cu using(customer_id) group by 1 order by 1")
