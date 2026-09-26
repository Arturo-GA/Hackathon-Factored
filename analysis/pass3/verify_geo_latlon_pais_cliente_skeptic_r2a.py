import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('##',t), print(con.execute(s).df().to_string(), '\n'))
for t in ['tx','cu','br','pr']:
    print(t, [ (r[0], r[1]) for r in con.execute(f"describe {t}").fetchall()])
q("cu country", "select country, count(*) n from cu group by 1 order by 2 desc")
q("tx country / country_raw", "select country, country_raw, count(*) n from tx group by all order by 1,2")
q("br country", "select country, count(*) n, count(distinct city) ncity, sum((lat=0 and lon=0)::int) zero, sum((lat is null)::int) latnull from br group by 1")
q("pr currency x cust country", "select cu.country, p.currency, count(*) n from pr p join cu using(customer_id) group by all order by 1,2")
