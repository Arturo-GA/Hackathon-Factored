import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('##',t), print(con.execute(s).df().to_string(), '\n'))
q("tx coords vs branch coords (ATM/Branch rows with both)", """select cu.country cc, count(*) n, round(corr(t.lat, b.lat),4) corr_lat, round(corr(t.lon, b.lon),4) corr_lon,
  round(avg((abs(t.lat-b.lat)<=1 and abs(t.lon-b.lon)<=1)::int),4) within1deg_of_branch
  from tx t join cu using(customer_id) join br b on b.branch_id=t.branch_id where t.lat is not null and t.lon is not null group by 1 order by 1""")
q("ATM tx at branches without ATM", """select b.has_atms, count(*) n, round(count(*)/sum(count(*)) over (),4) share_tx from tx t join br b using(branch_id) where t.channel='ATM' group by 1""")
q("br has_atms share", "select has_atms, count(*) n, round(count(*)/sum(count(*)) over (),4) share_br from br group by 1")
# AUC of |offset| distance for fraud and declined (rank-based, SQL)
for tgt in ["fraud", "status='Declined'"]:
    r = con.execute(f"""with g as (select ({tgt})::int y,
       sqrt(pow(t.lat-(case cu.country when 'Argentina' then -34.6037 when 'Colombia' then 4.711 else 0 end),2)
          + pow(t.lon-(case cu.country when 'Argentina' then -58.3816 when 'Colombia' then -74.0721 else 0 end),2)) d
       from tx t join cu using(customer_id) where t.lat is not null and t.lon is not null),
      r as (select y, rank() over (order by d) rk from g)
      select sum(y) npos, count(*)-sum(y) nneg, (sum(rk*y) - sum(y)*(sum(y)+1)/2)/(sum(y)*(count(*)-sum(y))) auc from r""").fetchone()
    print(f"AUC dist-to-center -> {tgt}: npos={r[0]} nneg={r[1]} auc={r[2]:.4f}")
