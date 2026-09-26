"""Verificador escéptico: behavior_comercios_sin_suscripciones.
Parte A: reglas comercio->mcat, mcat=tcat, comercio solo en Purchase, patrón de faltantes (¿sirve imputar?)."""
import duckdb, pandas as pd
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

print("== A1 catálogo: distintos crudos vs normalizados ==")
print(q("""SELECT count(DISTINCT merchant_name) n_raw, count(DISTINCT lower(trim(merchant_name))) n_norm,
          count(DISTINCT mcat) n_mcat, count(DISTINCT tcat) n_tcat, count(*) n FROM tx"""))

print("== A2 comercio -> #mcat distintas (no nulas), filas con mcat nula ==")
print(q("""SELECT merchant_name, count(DISTINCT mcat) n_mcat, any_value(mcat) mcat, count(*) n,
          sum((mcat IS NULL)::INT) mcat_null, sum((tcat IS NULL)::INT) tcat_null,
          sum((tcat IS NOT NULL AND mcat IS NOT NULL AND tcat<>mcat)::INT) tcat_ne_mcat
        FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1 ORDER BY 3,1"""))

print("== A3 por ttype: presencia de merchant/mcat/tcat ==")
print(q("""SELECT ttype, count(*) n, count(merchant_name) n_merch, count(mcat) n_mcat, count(tcat) n_tcat,
          sum((tcat IS NOT NULL AND mcat IS NOT NULL AND tcat<>mcat)::INT) n_tcat_ne_mcat
        FROM tx GROUP BY 1 ORDER BY 2 DESC"""))

print("== A4 patrón conjunto de faltantes en Purchase (merchant, mcat, tcat) ==")
print(q("""SELECT (merchant_name IS NULL) m_null, (mcat IS NULL) mc_null, (tcat IS NULL) tc_null, count(*) n,
          round(100*count(*)/sum(count(*)) OVER (),2) pct
        FROM tx WHERE ttype='Purchase' GROUP BY 1,2,3 ORDER BY 4 DESC"""))

print("== A5 valores de tcat por ttype (top) ==")
print(q("""SELECT ttype, tcat, count(*) n FROM tx GROUP BY 1,2 ORDER BY 1,3 DESC"""))

print("== A6 mcat cuando merchant es nulo ==")
print(q("""SELECT ttype, mcat, count(*) n FROM tx WHERE merchant_name IS NULL AND mcat IS NOT NULL GROUP BY 1,2 ORDER BY 3 DESC LIMIT 20"""))
