import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q=lambda t,s: (print('##',t), print(con.execute(s).df().to_string(), '\n'))
con.execute("""create temp table c as select t.channel, t.ttype, t.country_raw cr, t.country tc, t.city tcity, t.status, t.fraud, t.lat, t.branch_id,
   cu.country cc, cu.city ccity from tx t join cu using(customer_id)""")
q("country_raw x customer country", "pivot (select cr, cc from c) on cc using count(*) group by cr order by cr")
q("customer tx totals", "select cc, count(*) n from c group by 1 order by 1")
q("city behaviour by customer country x country_raw", """select cc, cr, count(*) n, round(avg((tcity is null)::int),4) city_null,
  round(avg((tcity=ccity)::int) filter (where tcity is not null),4) city_eq_cust,
  round(avg((tcity in (select distinct city from cu where country=c.cc))::int) filter (where tcity is not null),4) city_in_home_country
  from c group by all order by 1,2""")
q("foreign tx: city values sample", """select cc, tc, tcity, count(*) n from c where tc<>cc group by all order by n desc limit 12""")
q("domestic: city<>customer city, by country_raw", """select cc, cr, count(*) n_dom_citynn, sum((tcity<>ccity)::int) n_diff, round(avg((tcity<>ccity)::int),4) rate_diff
  from c where tc=cc and tcity is not null group by all order by 1,2""")
q("domestic city = customer city overall", """select count(*) n, round(avg((tcity=ccity)::int),4) same from c where tc=cc and tcity is not null""")
q("foreign rate by channel", "select channel, count(*) n, round(avg((tc<>cc)::int),4) foreign_rate from c group by 1 order by 1")
q("foreign rate by ttype", "select ttype, count(*) n, round(avg((tc<>cc)::int),4) foreign_rate from c group by 1 order by 1")
q("foreign rate by customer country", "select cc, count(*) n, round(avg((tc<>cc)::int),4) foreign_rate from c group by 1 order by 1")
q("foreign vs fraud/declined", "select (tc<>cc) foreign_, count(*) n, round(avg(fraud::int)*1000,3) fraud_pm, round(avg((status='Declined')::int),4) decl from c group by 1")
