"""Verificador escéptico (parte E): ¿el comercio/mcat informa algo más (monto, canal, estado, fraude)? ¿qué comercio da 3.99%?
¿las tasas de imputación reales?"""
import duckdb, pandas as pd, numpy as np
from scipy.stats import chi2_contingency
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 100)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

def V(df, a, b):
    ct = df.pivot_table(index=a, columns=b, values="n", aggfunc="sum").fillna(0).values
    chi2 = chi2_contingency(ct)[0]; n = ct.sum()
    return np.sqrt(chi2 / (n * (min(ct.shape) - 1)))

print("== E1 monto por mcat (mediana normalizada por moneda: mediana_mcat / mediana_moneda) ==")
m = q("""WITH b AS (SELECT currency, mcat, amount FROM tx WHERE ttype='Purchase' AND mcat IS NOT NULL),
 g AS (SELECT currency, median(amount) mg FROM b GROUP BY 1)
 SELECT b.currency, mcat, count(*) n, round(median(amount)/any_value(mg),3) ratio_med, round(avg(amount)/any_value(mg),3) ratio_mean
 FROM b JOIN g USING(currency) GROUP BY 1,2 ORDER BY 1,2""")
print(m.pivot(index="mcat", columns="currency", values="ratio_med"))
for col in ["channel", "status", "fraud"]:
    d = q(f"SELECT merchant_name, {col} c, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2")
    print(f"V(comercio, {col}) = {V(d,'merchant_name','c'):.4f}")
print(q("""SELECT merchant_name, round(100*avg(fraud::INT),3) pct_fraud, round(100*avg((status='Declined')::INT),2) pct_decl, count(*) n
           FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1 ORDER BY 2 DESC""").agg({"pct_fraud":["min","max"],"pct_decl":["min","max"]}))

print("== E2 comercio con menor % montos <5% en consecutivas ==")
print(q("""WITH s AS (SELECT product_id, merchant_name, amount, lag(amount) OVER (PARTITION BY product_id, merchant_name ORDER BY ts) pamt
   FROM tx WHERE merchant_name IS NOT NULL)
 SELECT merchant_name, count(*) n, round(100*avg((abs(amount/pamt-1)<0.05)::INT),2) pct FROM s WHERE pamt IS NOT NULL GROUP BY 1 ORDER BY 3 LIMIT 4"""))

print("== E3 imputación: nulos en Purchase recuperables ==")
print(q("""SELECT
  sum((mcat IS NULL)::INT) mcat_null,
  sum((mcat IS NULL AND merchant_name IS NOT NULL)::INT) mcat_desde_comercio,
  sum((mcat IS NULL AND (merchant_name IS NOT NULL OR tcat IS NOT NULL))::INT) mcat_desde_comercio_o_tcat,
  sum((tcat IS NULL)::INT) tcat_null,
  sum((tcat IS NULL AND merchant_name IS NOT NULL)::INT) tcat_desde_comercio,
  sum((tcat IS NULL AND (merchant_name IS NOT NULL OR mcat IS NOT NULL))::INT) tcat_desde_comercio_o_mcat,
  sum((merchant_name IS NULL)::INT) merch_null
 FROM tx WHERE ttype='Purchase'"""))
