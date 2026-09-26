"""hunt_26: la V de Cramer country x decil de credit_score (0.105) y inc_null x cs_dec (0.080) de hunt_07:
 ¿credit_score depende del pais? ¿los nulos de income y credit_score van juntos?
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_26_cs_country.py
"""
import duckdb
import pandas as pd
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='300MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
q = lambda s: con.execute(s).df()
print(q("""SELECT country, segment, count(*) n, avg(credit_score) cs_mean, stddev(credit_score) cs_sd, min(credit_score) mn, max(credit_score) mx,
  avg(CASE WHEN credit_score IS NULL THEN 1.0 ELSE 0 END) cs_null, avg(CASE WHEN income IS NULL THEN 1.0 ELSE 0 END) inc_null
  FROM cu GROUP BY 1,2 ORDER BY 1,2""").round(3).to_string())
print(q("""SELECT country, count(*) n, avg(credit_score) cs_mean, avg(CASE WHEN credit_score IS NULL THEN 1.0 ELSE 0 END) cs_null,
  avg(CASE WHEN segment='Basic' THEN 1.0 ELSE 0 END) basic, avg(CASE WHEN segment='Plus' THEN 1.0 ELSE 0 END) plus,
  avg(CASE WHEN segment='Premium' THEN 1.0 ELSE 0 END) premium, avg(CASE WHEN segment='Student' THEN 1.0 ELSE 0 END) student
  FROM cu GROUP BY 1 ORDER BY 1""").round(4).to_string())
print('nulos conjuntos income x credit_score:')
print(q("""SELECT CASE WHEN income IS NULL THEN 'inc_null' ELSE 'inc_ok' END i, CASE WHEN credit_score IS NULL THEN 'cs_null' ELSE 'cs_ok' END c, count(*) n
  FROM cu GROUP BY 1,2 ORDER BY 1,2""").to_string())
print('credit_score: rango global y por pais (min/max), redondeo:')
print(q("""SELECT country, min(credit_score) mn, max(credit_score) mx, avg(CASE WHEN credit_score = round(credit_score) THEN 1.0 ELSE 0 END) int_share,
  count(DISTINCT credit_score) ndist FROM cu GROUP BY 1""").to_string())
