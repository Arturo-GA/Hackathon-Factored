import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
for r in con.execute("""select currency, count(*), count(claimed), min(claimed), round(avg(claimed),2), max(claimed),
  sum(claimed/(case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end) > 10000)::bigint over_transfer_cap,
  sum(claimed/(case currency when 'COP' then 4000 when 'ARS' then 350 else 1 end) > 500)::bigint over_purchase_cap
  from cp group by 1 order by 1""").fetchall(): print(r)
