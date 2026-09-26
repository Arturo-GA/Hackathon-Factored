"""H7/H8: semantica ISO de codigos vs tipo/canal; Adjustments; fraude vs estado; process_date."""
import duckdb, pandas as pd
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
pd.set_option('display.width',250)
print("== process_date vs fecha de ts por hora ==")
print(q("""select hour(ts) h, avg(case when process_date<cast(ts as date) then 1 else 0 end) prev_day,
 avg(case when process_date=cast(ts as date) then 1 else 0 end) same from tx group by 1 order by 1""").T.round(3).to_string())
print(q("""select date_diff('day', cast(ts as date), process_date) d, count(*) from tx group by 1 order by 1""").to_string())
print("== fraude vs estado ==")
print(q("""select fraud, status, count(*) n from tx group by 1,2 order by 1,2""").pivot(index='fraud',columns='status',values='n').to_string())
print(q("""select case when fscore is null then 'nulo' when fscore>=50 then '>=50' else '<50' end fs, status, count(*) n from tx group by 1,2""").pivot(index='fs',columns='status',values='n').to_string())
print("== codigo x ttype (no aprobadas) ==")
print(q("""select ttype, coalesce(code,'NA') code, count(*) n from tx where status='Declined' group by 1,2""").pivot(index='ttype',columns='code',values='n').to_string())
print("== codigo x channel (no aprobadas) ==")
print(q("""select channel, coalesce(code,'NA') code, count(*) n from tx where status='Declined' group by 1,2""").pivot(index='channel',columns='code',values='n').to_string())
print("== ttype x channel ==")
print(q("""select ttype, channel, count(*) n from tx group by 1,2""").pivot(index='ttype',columns='channel',values='n').to_string())
print("== Adjustment: perfil ==")
print(q("""select ttype, count(*) n, avg(case when amount<0 then 1 else 0 end) neg, min(amount) mn, median(amount) med, max(amount) mx,
  avg(case when merchant_name is null then 1 else 0 end) merch_null, avg(case when tcat is null then 1 else 0 end) tcat_null,
  avg(case when branch_id is null then 1 else 0 end) br_null, avg(case when lat is null then 1 else 0 end) lat_null,
  avg(case when round(amount)=amount then 1 else 0 end) entero
 from tx group by 1 order by 1""").round(3).to_string())
print(q("""select ttype, coalesce(tcat,'NA') tcat, count(*) n from tx group by 1,2""").pivot(index='tcat',columns='ttype',values='n').to_string())
print(q("""select ttype, coalesce(mcat,'NA') mcat, count(*) n from tx group by 1,2""").pivot(index='mcat',columns='ttype',values='n').to_string())
print(q("""select ttype, channel, count(*) n, median(amount_usd) med_usd from tx where ttype='Adjustment' group by 1,2 order by 3 desc""").to_string())
# ptype de adjustments
print(q("""select p.ptype, t.ttype, count(*) n from tx t join pr p using(product_id) group by 1,2""").pivot(index='ptype',columns='ttype',values='n').to_string())
