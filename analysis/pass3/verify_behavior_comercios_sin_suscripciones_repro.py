"""Verificación independiente: behavior_comercios_sin_suscripciones.
Parte 1: catálogo de comercios, mapeo comercio->mcat, mcat vs tcat, presencia por ttype,
faltantes conjuntos (¿se puede imputar mcat/tcat desde merchant?)."""
import duckdb
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 200)

con = duckdb.connect("data/analysis.duckdb", read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

print("== 1. Catálogo de comercios ==")
print(q("""SELECT count(*) n_tx, count(merchant_name) n_merch, count(DISTINCT merchant_name) n_distinct_merch,
           count(DISTINCT mcat) n_distinct_mcat, count(DISTINCT tcat) n_distinct_tcat FROM tx"""))

print("\n== 2. Comercio -> mcat (distintos mcat no nulos por comercio, y nulos) ==")
m = q("""SELECT merchant_name, count(*) n, count(mcat) n_mcat_nonnull,
          count(DISTINCT mcat) n_mcat_distinct, min(mcat) mcat_min, max(mcat) mcat_max,
          count(tcat) n_tcat_nonnull, count(DISTINCT tcat) n_tcat_distinct, min(tcat) tcat_min, max(tcat) tcat_max,
          count(DISTINCT ttype) n_ttype, min(ttype) ttype
       FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1 ORDER BY mcat_min, 1""")
print(m.to_string())
print("comercios con >1 mcat:", int((m.n_mcat_distinct > 1).sum()), "| con >1 tcat:", int((m.n_tcat_distinct > 1).sum()))

print("\n== 3. Presencia de merchant/mcat/tcat por ttype ==")
print(q("""SELECT ttype, count(*) n, count(merchant_name) n_merch, round(avg((merchant_name IS NOT NULL)::INT),4) p_merch,
          count(mcat) n_mcat, count(tcat) n_tcat, count(DISTINCT tcat) n_tcat_vals
        FROM tx GROUP BY 1 ORDER BY 2 DESC""").to_string())

print("\n== 4. tcat por ttype (valores) ==")
print(q("""SELECT ttype, tcat, count(*) n FROM tx GROUP BY 1,2 ORDER BY 1,3 DESC""").to_string())

print("\n== 5. mcat vs tcat cuando ambos no nulos (todas las filas) ==")
print(q("""SELECT count(*) n_both, sum((mcat=tcat)::INT) n_equal, sum((mcat<>tcat)::INT) n_diff
        FROM tx WHERE mcat IS NOT NULL AND tcat IS NOT NULL"""))
print(q("""SELECT ttype, count(*) n_both, sum((mcat=tcat)::INT) n_equal FROM tx
        WHERE mcat IS NOT NULL AND tcat IS NOT NULL GROUP BY 1"""))

print("\n== 6. mcat presente sin merchant? (todas las filas) ==")
print(q("""SELECT (merchant_name IS NOT NULL) has_merch, (mcat IS NOT NULL) has_mcat, (tcat IS NOT NULL) has_tcat, ttype='Purchase' is_purchase,
          count(*) n FROM tx GROUP BY ALL ORDER BY is_purchase DESC, has_merch DESC, has_mcat DESC, has_tcat DESC""").to_string())

print("\n== 7. Faltantes conjuntos en compras: ¿cuántos mcat/tcat nulos son imputables desde merchant? ==")
print(q("""SELECT count(*) n_purch,
          sum((mcat IS NULL)::INT) mcat_null, sum((mcat IS NULL AND merchant_name IS NOT NULL)::INT) mcat_null_imputable,
          sum((tcat IS NULL)::INT) tcat_null, sum((tcat IS NULL AND merchant_name IS NOT NULL)::INT) tcat_null_imputable_from_merch,
          sum((tcat IS NULL AND mcat IS NOT NULL)::INT) tcat_null_imputable_from_mcat,
          sum((merchant_name IS NULL)::INT) merch_null,
          sum((merchant_name IS NULL AND mcat IS NULL AND tcat IS NULL)::INT) all3_null,
          sum((merchant_name IS NULL AND (mcat IS NOT NULL OR tcat IS NOT NULL))::INT) merch_null_but_cat
        FROM tx WHERE ttype='Purchase'"""))

print("\n== 8. Categorías de compras: tcat sin merchant; ¿hay tcat de compra que no correspondan a ningún comercio? ==")
print(q("""SELECT tcat, count(*) n, count(merchant_name) n_merch, count(DISTINCT merchant_name) n_merch_vals
        FROM tx WHERE ttype='Purchase' GROUP BY 1 ORDER BY 2 DESC""").to_string())

print("\n== 9. Canal de las compras con/sin merchant ==")
print(q("""SELECT channel, count(*) n, count(merchant_name) n_merch FROM tx WHERE ttype='Purchase' GROUP BY 1 ORDER BY 2 DESC""").to_string())

print("\n== 10. Frecuencia de comercios: global y por país (¿uniforme? ¿depende del país?) ==")
f = q("""SELECT merchant_name, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1 ORDER BY 2 DESC""")
f["p"] = f.n / f.n.sum()
print(f.to_string())
fc = q("""SELECT country, merchant_name, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2""")
ct = fc.pivot_table(index="merchant_name", columns="country", values="n", fill_value=0)
from scipy.stats import chi2_contingency
chi2, pval, dof, _ = chi2_contingency(ct.values)
nn = ct.values.sum(); r, c = ct.shape
V = (chi2 / (nn * (min(r, c) - 1))) ** 0.5
print("país x comercio: chi2=%.1f dof=%d p=%.3g V=%.4f  (n=%d)" % (chi2, dof, pval, V, nn))
