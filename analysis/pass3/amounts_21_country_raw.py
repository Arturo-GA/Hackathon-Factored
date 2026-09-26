import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
q("pivot (select t.country_raw, cu.country cc from tx t join cu using(customer_id)) on cc using count(*) group by country_raw order by country_raw")
# foreign tx: city vs customer city, branch country
q("""select (t.country<>cu.country) foreign_, count(*) n, avg((t.city=cu.city)::int) same_city, avg((t.city is null)::int) city_null,
 avg((b.country=cu.country)::int) branch_in_home, avg((b.country=t.country)::int) branch_in_txcountry, avg(t.fraud::int)*1000 fraud_pm, avg((t.status='Declined')::int) decl
 from tx t join cu using(customer_id) left join br b on b.branch_id=t.branch_id group by all""")
# for foreign: which ttype/channel? any differences
q("""select t.channel, avg((t.country<>cu.country)::int) foreign_rate, count(*) n from tx t join cu using(customer_id) group by 1""")
q("""select t.ttype, avg((t.country<>cu.country)::int) foreign_rate, count(*) n from tx t join cu using(customer_id) group by 1""")
