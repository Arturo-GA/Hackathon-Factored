"""Verificador escéptico (reintento) — parte A: procedencia (CSV crudo / bronze) y regla central.
¿`fraud` o `fscore` son derivados en nuestro ETL? ¿los nulos son fallos de TRY_CAST? ¿otras grafías de True?"""
import duckdb, pandas as pd
pd.set_option('display.width', 220); pd.set_option('display.max_columns', 40)
con = duckdb.connect()
con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

RAW = "read_csv('data/raw/transactions/*/*/*/*.csv', all_varchar=true, header=true, union_by_name=true)"
print('== A1. CSV crudo: grafías de is_fraud y formato de fraud_score ==')
print(q(f"""SELECT is_fraud, count(*) n,
   count(*) FILTER (WHERE fraud_score IS NULL OR trim(fraud_score)='') score_vacio,
   count(*) FILTER (WHERE fraud_score IS NOT NULL AND trim(fraud_score)<>'' AND TRY_CAST(fraud_score AS DOUBLE) IS NULL) score_no_parsea,
   max(TRY_CAST(fraud_score AS DOUBLE)) mx, min(TRY_CAST(fraud_score AS DOUBLE)) mn,
   count(*) FILTER (WHERE TRY_CAST(fraud_score AS DOUBLE)>30) gt30
 FROM {RAW} GROUP BY 1 ORDER BY 1""").to_string(index=False))
print(q(f"""SELECT length(split_part(fraud_score,'.',2)) n_dec, count(*) n FROM {RAW}
 WHERE fraud_score IS NOT NULL AND trim(fraud_score)<>'' GROUP BY 1 ORDER BY 1""").to_string(index=False))

B = "'data/bronze/transactions.parquet'"
print('\n== A2. Bronze: mismas comprobaciones ==')
print(q(f"""SELECT is_fraud, count(*) n, count(DISTINCT transaction_id) nid,
   count(*) FILTER (WHERE fraud_score IS NULL OR trim(fraud_score)='') score_vacio,
   count(*) FILTER (WHERE fraud_score IS NOT NULL AND trim(fraud_score)<>'' AND TRY_CAST(fraud_score AS DOUBLE) IS NULL) score_no_parsea
 FROM {B} GROUP BY 1 ORDER BY 1""").to_string(index=False))

print('\n== A3. Base tipada: conteos por clase ==')
con.execute("ATTACH 'data/analysis.duckdb' AS a (READ_ONLY)")
print(q("""SELECT fraud, count(*) n, count(DISTINCT transaction_id) nid, count(fscore) n_score,
   min(fscore) mn, max(fscore) mx, count(*) FILTER (WHERE fscore=30) eq30, count(*) FILTER (WHERE fscore=0) eq0,
   count(*) FILTER (WHERE fscore>30) gt30, min(fscore) FILTER (WHERE fscore>30) min_gt30,
   max(fscore) FILTER (WHERE fscore<=30) max_le30
 FROM a.tx GROUP BY 1 ORDER BY 1""").to_string(index=False))

print('\n== A4. Tramos ==')
t = q("""SELECT CASE WHEN fscore IS NULL THEN 'nulo' WHEN fscore<=30 THEN 'le30' ELSE 'gt30' END tramo,
   count(*) n, sum(fraud::int) f FROM a.tx GROUP BY 1 ORDER BY 1""").set_index('tramo')
t['pct'] = 100 * t.f / t.n
print(t)
N, F = t.n.sum(), t.f.sum()
print(f'tasa base = {100*F/N:.4f}%  (n={N}, fraude={F})')

print('\n== A5. Estabilidad por mes: max legit y legit>30 por mes (resumen) ==')
m = q("""SELECT strftime(ts,'%Y-%m') ym, max(fscore) FILTER (WHERE NOT fraud) max_leg,
   count(*) FILTER (WHERE NOT fraud AND fscore>30) leg_gt30, count(*) FILTER (WHERE fraud AND fscore>30) fr_gt30,
   count(*) FILTER (WHERE fraud AND fscore IS NOT NULL) fr_sc
 FROM a.tx GROUP BY 1 ORDER BY 1""")
print('meses:', len(m), ' max legit en todo mes:', m.max_leg.max(), ' min del max legit:', m.max_leg.min(),
      ' legit>30 total:', m.leg_gt30.sum(), ' meses con legit>30:', (m.leg_gt30 > 0).sum())
print('fraude>30 / fraude con score por mes: min %.2f max %.2f' % ((m.fr_gt30/m.fr_sc).min(), (m.fr_gt30/m.fr_sc).max()))
