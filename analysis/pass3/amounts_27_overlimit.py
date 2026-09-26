import duckdb, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda s: print(con.execute(s).df().to_string(), '\n')
q("""select ptype, count(*) n, avg((bal>credit_limit)::int) over_limit, corr(bal/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end), credit_limit/(case currency when 'ARS' then 350 when 'COP' then 4000 else 1 end)) c_usd from pr where credit_limit is not null group by 1""")
q("""select (p.bal>p.credit_limit) over_limit, count(*) n, avg((t.status='Declined')::int) decl, avg((t.code='51')::int) c51, avg((t.code='54')::int) c54
 from tx t join pr p using(product_id) where p.ptype='Tarjeta Crédito' group by 1""")
# expired product (code 54 = expired card) vs tx after expires
q("""select (t.ts::date > p.expires) after_exp, count(*) n, avg((t.code='54')::int) c54, avg((t.status='Declined')::int) decl from tx t join pr p using(product_id) where p.expires is not null group by 1""")
# tx before product opened
q("""select (t.ts::date < p.opened) before_open, count(*) n from tx t join pr p using(product_id) group by 1""")
