"""Verificación independiente de 'fraud_geo_inutilizable' (parte 1: cobertura y centroides)."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(t, s):
    print('==', t); print(con.execute(s).df().to_string(index=False), '\n')

q('cobertura global de coordenadas', """
select count(*) n,
  round(100*avg((lat is not null)::int),2) pct_lat,
  round(100*avg((lon is not null)::int),2) pct_lon,
  round(100*avg((lat is not null and lon is not null)::int),2) pct_both,
  round(100*avg((lat is not null or lon is not null)::int),2) pct_any,
  round(100*avg((lat is null and lon is null)::int),2) pct_none
from tx""")

q('cobertura por canal', """
select channel, count(*) n,
  round(100*avg((lat is not null)::int),2) pct_lat,
  round(100*avg((lon is not null)::int),2) pct_lon,
  round(100*avg((lat is not null and lon is not null)::int),2) pct_both,
  round(100*avg((branch_id is not null)::int),2) pct_branch
from tx group by 1 order by 1""")

q('valores de country (tx) y country (cu)', """
select 'tx' src, country, count(*) n from tx group by all
union all select 'cu', country, count(*) from cu group by all order by 1,3 desc""")
