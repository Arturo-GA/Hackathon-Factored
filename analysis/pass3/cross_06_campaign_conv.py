# H5: conversion de campana -> producto abierto cerca de conv_ts / tx de ese valor?
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
print(q("select promoted_product, count(*) from mc group by 1 order by 2 desc"))
print(q("""select count(*) n, sum(conv::int) nconv, count(conv_ts) nts, count(conv_value) nval,
   quantile_cont(conv_value,[0.1,0.5,0.9]) qv from cs"""))
con.execute("""create temp table cv as select cs.send_id, cs.customer_id, cs.ts, cs.conv_ts, round(cs.conv_value,2) cv, mc.promoted_product, mc.campaign_type
  from cs join mc using(campaign_id) where conv""")
print(q("select count(*) from cv"))
# product opened within +-7d of conv_ts (any type / promoted type)
print(q("""select count(*) n,
  avg((exists(select 1 from pr p where p.customer_id=cv.customer_id and abs(date_diff('day', p.opened, cv.conv_ts::date))<=7))::int) any7,
  avg((exists(select 1 from pr p where p.customer_id=cv.customer_id and p.ptype=cv.promoted_product and abs(date_diff('day', p.opened, cv.conv_ts::date))<=30))::int) same30,
  avg((exists(select 1 from pr p where p.customer_id=cv.customer_id and p.ptype=cv.promoted_product))::int) has_type
 from cv"""))
# placebo: non-converted sends, using ts+ median lag
print(q("""select count(*) n,
  avg((exists(select 1 from pr p where p.customer_id=s.customer_id and abs(date_diff('day', p.opened, s.ts::date + 3))<=7))::int) any7,
  avg((exists(select 1 from pr p join mc on mc.campaign_id=s.campaign_id where p.customer_id=s.customer_id and p.ptype=mc.promoted_product))::int) has_type
 from (select * from cs where not conv using sample 50000) s"""))
print(q("select quantile_cont(date_diff('hour', ts, conv_ts),[0,0.1,0.5,0.9,1]) from cv"))
# conv_value vs tx of customer after conv (exact)
print(q("""select count(*) n, avg((exists(select 1 from tx t where t.customer_id=cv.customer_id and round(t.amount,2)=cv.cv))::int) exact_any,
  avg((exists(select 1 from tx t where t.customer_id=cv.customer_id and t.ts between cv.conv_ts - interval 3 day and cv.conv_ts + interval 3 day))::int) tx3d
 from (select * from cv using sample 5000) cv"""))
