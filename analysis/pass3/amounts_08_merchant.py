import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
q("""select ttype, count(*) n, avg((tcat is not null)::int) tcat_nn, avg((mcat is not null)::int) mcat_nn, avg((merchant_name is not null)::int) merch_nn,
 avg((branch_id is not null)::int) br_nn, avg((lat is not null)::int) lat_nn, avg((city is not null)::int) city_nn from tx group by all""")
q("""select channel, count(*) n, avg((tcat is not null)::int) tcat_nn, avg((mcat is not null)::int) mcat_nn, avg((merchant_name is not null)::int) merch_nn,
 avg((branch_id is not null)::int) br_nn, avg((lat is not null)::int) lat_nn from tx group by all""")
# ttype x channel
q("""pivot (select ttype, channel from tx) on channel using count(*) group by ttype""")
# mcat vs tcat when both present
q("""select mcat, tcat, count(*) n from tx where ttype='Purchase' group by all order by 1,2""")
# merchant -> mcat mapping
q("""select count(distinct merchant_name) nm, count(distinct (merchant_name, mcat)) nmm from tx where merchant_name is not null""")
q("""select merchant_name, count(distinct mcat) nc, string_agg(distinct mcat, ',') cats, count(*) n from tx where merchant_name is not null group by 1 order by n desc limit 40""")
