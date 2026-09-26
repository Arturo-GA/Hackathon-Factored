"""hunt_12: detalle de reglas detectadas en el barrido de V de Cramer (hunt_07):
 (1) hora -> process_date (corte operativo 06:00), (2) canal -> branch_id / lat-lon, ttype x canal,
 (3) formato de product_number por ptype + Luhn en tarjetas, (4) flag repeat de reclamos vs historial,
 (5) resumen V max de atributos cliente/producto vs campos de tx.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_12_rules_probe.py
"""
import duckdb
import pandas as pd
pd.set_option('display.width', 220); pd.set_option('display.max_rows', 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='500MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

print('(1) lag process_date por hora')
print(con.execute("""SELECT hour(ts) h, count(*) n, avg(date_diff('day', CAST(ts AS DATE), process_date)) lag_avg,
  min(date_diff('day', CAST(ts AS DATE), process_date)) lag_min, max(date_diff('day', CAST(ts AS DATE), process_date)) lag_max
  FROM tx GROUP BY 1 ORDER BY 1""").df().to_string())
for tbl in ['tx', 'cc', 'cp']:
    print(tbl, 'regla process_date = date(ts - 6h):', con.execute(f"""SELECT count(*) n,
      avg(CASE WHEN process_date = CAST(ts - INTERVAL 6 HOUR AS DATE) THEN 1.0 ELSE 0 END) ok_6h,
      avg(CASE WHEN process_date = CAST(ts AS DATE) THEN 1.0 ELSE 0 END) ok_same FROM {tbl}""").fetchall())
print(con.execute("""SELECT count(*) FILTER (WHERE process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE)) viol,
  min(ts) FILTER (WHERE process_date <> CAST(ts - INTERVAL 6 HOUR AS DATE)) ex FROM tx""").fetchall())

print('(2) campos presentes por canal')
print(con.execute("""SELECT channel, count(*) n, avg(CASE WHEN branch_id IS NOT NULL THEN 1.0 ELSE 0 END) has_branch,
  avg(CASE WHEN lat IS NOT NULL THEN 1.0 ELSE 0 END) has_latlon, avg(CASE WHEN merchant_name IS NOT NULL THEN 1.0 ELSE 0 END) has_merch,
  avg(CASE WHEN tcat IS NOT NULL THEN 1.0 ELSE 0 END) has_tcat, avg(CASE WHEN city IS NOT NULL THEN 1.0 ELSE 0 END) has_city
  FROM tx GROUP BY 1 ORDER BY 2 DESC""").df().to_string())
print(con.execute("""SELECT ttype, channel, count(*) n FROM tx GROUP BY 1,2""").df()
      .pivot(index='ttype', columns='channel', values='n').fillna(0).astype(int).to_string())

print('(3) formato product_number')
print(con.execute("""SELECT ptype, length(product_number) len, left(product_number,1) p1, count(*) n, min(product_number) ex_min, max(product_number) ex_max
  FROM pr GROUP BY 1,2,3 ORDER BY 1,2,3""").df().to_string())
cards = con.execute("SELECT ptype, product_number FROM pr WHERE ptype IN ('Tarjeta Crédito','Tarjeta Débito') USING SAMPLE 50000 ROWS").df()


def luhn(s):
    ds = [int(c) for c in s][::-1]
    tot = sum(d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2) for i, d in enumerate(ds))
    return tot % 10 == 0


cards['luhn'] = cards.product_number.map(luhn)
print('Luhn valido (esperado 10% si aleatorio):', cards.groupby('ptype').luhn.mean().round(4).to_dict(), 'n=', len(cards))
print('prefijos 2 digitos tarjetas:', cards.product_number.str[:2].value_counts().head(12).to_dict())

print('(4) repeat de reclamos vs reclamos previos del mismo cliente')
print(con.execute("""WITH c AS (SELECT customer_id, ts, repeat,
   count(*) OVER (PARTITION BY customer_id ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) nprior,
   count(*) OVER (PARTITION BY customer_id) tot FROM cp)
  SELECT least(nprior,3) nprior, least(tot,4) tot, count(*) n, avg(CASE WHEN repeat THEN 1.0 ELSE 0 END) repeat_rate FROM c GROUP BY 1,2 ORDER BY 1,2""").df().to_string())

print('(5) V max atributos cliente/producto x campos tx (muestra 800k de hunt_07)')
r = pd.read_csv('analysis/pass3/hunt_cache/hunt_07_cramer.csv')
custattrs = ['segment', 'gender', 'occupation', 'cstatus', 'mkt', 'education', 'marital', 'age_dec', 'papp', 'opening_channel', 'popen_yr']
txf = ['ttype', 'tcat', 'channel', 'mcat', 'tcountry', 'tcity', 'status', 'code', 'fraud', 'fscore_b', 'merchant', 'has_branch',
       'has_latlon', 'hr', 'dow', 'dom', 'amt_dec', 'amt_round', 'home', 'proc_lag']
sub = r[(r.lvl == 'tx') & (((r.a.isin(custattrs)) & (r.b.isin(txf))) | ((r.b.isin(custattrs)) & (r.a.isin(txf))))]
print('pares:', len(sub), 'V max:', round(sub.V.max(), 4), 'NMI max:', round(sub.NMI.max(), 5))
sub2 = r[(r.lvl == 'tx') & ((r.a.isin(['status', 'code', 'fraud'])) | (r.b.isin(['status', 'code', 'fraud'])))].sort_values('V', ascending=False)
print(sub2.head(8).to_string(index=False))
print(r[(r.lvl == 'tx') & (r.a.isin(['ttype', 'channel'])) & (r.b.isin(['ttype', 'channel']))].to_string(index=False))
