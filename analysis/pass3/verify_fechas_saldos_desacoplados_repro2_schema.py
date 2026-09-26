import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(title, s):
    print('==', title); print(con.execute(s).df().to_string(), '\n', flush=True)
q('tipos pr', "select column_name, data_type from information_schema.columns where table_name='pr' order by ordinal_position")
q('tipos tx', "select column_name, data_type from information_schema.columns where table_name='tx' and column_name in ('ts','process_date','amount','amount_usd','status','code','ttype','tcat','currency','product_id')")
q('pr por ptype', """select ptype, count(*) n, min(opened) min_open, max(opened) max_open, avg((expires is null)::int) exp_null,
   min(expires) min_exp, max(expires) max_exp, avg((credit_limit is not null)::int) has_lim, min(bal) minbal, avg((bal<0)::int) neg_bal
   from pr group by 1 order by 2 desc""")
q('rango tx', "select min(ts) mn, max(ts) mx, min(process_date) mnp, max(process_date) mxp, count(*) n, count(distinct product_id) nprod from tx")
q('tx sin producto en pr', "select count(*) n, sum((p.product_id is null)::int) no_prod from tx t left join pr p using(product_id)")
q('monto por ttype', "select ttype, count(*) n, min(amount) mn, max(amount) mx, avg((amount<0)::int) neg from tx group by 1 order by 2 desc")
q('tcat por ttype', "select ttype, tcat, count(*) n from tx group by all order by 1, 3 desc")
