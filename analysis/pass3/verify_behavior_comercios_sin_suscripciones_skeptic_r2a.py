"""Verificador escéptico (ronda 2, parte A): reglas comercio->mcat, mcat=tcat, comercio solo en Purchase,
patrón de nulos y rendimiento REAL de la imputación propuesta; ¿el faltante de comercio es estructural (canal/estado/país)?"""
import duckdb, pandas as pd, numpy as np
from scipy.stats import chi2_contingency
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

print("== A0 esquema tx ==")
print(q("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='tx'").to_string(index=False))

print("\n== A1 catálogo (crudo vs normalizado: lower/trim/strip_accents) ==")
print(q("""SELECT count(DISTINCT merchant_name) n_raw, count(DISTINCT strip_accents(lower(trim(merchant_name)))) n_norm,
          count(DISTINCT mcat) n_mcat, count(DISTINCT tcat) n_tcat, count(DISTINCT (merchant_name, mcat)) n_pairs_merch_mcat
        FROM tx""").to_string(index=False))

print("\n== A2 comercio -> mcat/tcat (distintos no nulos), nulos y ttype ==")
m = q("""SELECT merchant_name, count(*) n, count(DISTINCT mcat) k_mcat, min(mcat) mcat, count(DISTINCT tcat) k_tcat, min(tcat) tcat,
          sum((mcat IS NULL)::INT) mcat_null, sum((tcat IS NULL)::INT) tcat_null, count(DISTINCT ttype) k_ttype, min(ttype) ttype
        FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1 ORDER BY mcat, 1""")
print(m.to_string(index=False))
print("comercios con >1 mcat:", int((m.k_mcat>1).sum()), " >1 tcat:", int((m.k_tcat>1).sum()), " >1 ttype:", int((m.k_ttype>1).sum()))

print("\n== A3 presencia por ttype ==")
print(q("""SELECT ttype, count(*) n, count(merchant_name) n_merch, count(mcat) n_mcat, count(tcat) n_tcat,
          count(DISTINCT tcat) k_tcat, sum((mcat IS NOT NULL AND tcat IS NOT NULL)::INT) both_nn,
          sum((mcat IS NOT NULL AND tcat IS NOT NULL AND mcat<>tcat)::INT) mismatch
        FROM tx GROUP BY 1 ORDER BY 2 DESC""").to_string(index=False))

print("\n== A4 valores de tcat en Payment vs Purchase ==")
print(q("""SELECT tcat, sum((ttype='Purchase')::INT) purchase, sum((ttype='Payment')::INT) payment FROM tx
        WHERE ttype IN ('Purchase','Payment') GROUP BY 1 ORDER BY 1""").to_string(index=False))

print("\n== A5 Purchase: patrón conjunto de nulos (merchant, mcat, tcat) vs independencia ==")
pat = q("""SELECT (merchant_name IS NULL) m0, (mcat IS NULL) c0, (tcat IS NULL) t0, count(*) n FROM tx WHERE ttype='Purchase' GROUP BY ALL ORDER BY n DESC""")
N = pat.n.sum()
pm = pat[pat.m0].n.sum()/N; pc = pat[pat.c0].n.sum()/N; pt = pat[pat.t0].n.sum()/N
pat["pct"] = 100*pat.n/N
pat["pct_indep"] = 100*pat.apply(lambda r: (pm if r.m0 else 1-pm)*(pc if r.c0 else 1-pc)*(pt if r.t0 else 1-pt), axis=1)
print(pat.round(4).to_string(index=False))
print(f"marginales nulos Purchase: merchant={100*pm:.3f}% mcat={100*pc:.3f}% tcat={100*pt:.3f}%  N={N:,}")

print("\n== A6 imputación en Purchase: ¿cuánto recupera cada fuente? ==")
print(q("""WITH d AS (SELECT merchant_name, any_value(mcat) mc FROM tx WHERE merchant_name IS NOT NULL AND mcat IS NOT NULL GROUP BY 1)
  SELECT count(*) n,
   round(100*avg((t.mcat IS NULL)::INT),3) mcat_null,
   round(100*avg((coalesce(t.mcat, t.tcat) IS NULL)::INT),3) cat_null_tras_tcat,
   round(100*avg((coalesce(t.mcat, d.mc) IS NULL)::INT),3) cat_null_tras_dicc,
   round(100*avg((coalesce(t.mcat, t.tcat, d.mc) IS NULL)::INT),3) cat_null_tras_ambos,
   sum((coalesce(t.mcat, t.tcat, d.mc) IS NULL)::INT) n_cat_irrecuperable,
   round(100*avg((t.tcat IS NULL)::INT),3) tcat_null,
   round(100*avg((coalesce(t.tcat, t.mcat) IS NULL)::INT),3) tcat_null_tras_mcat,
   round(100*avg((t.merchant_name IS NULL)::INT),3) merch_null_no_imputable,
   sum((t.mcat IS NULL AND t.tcat IS NULL AND t.merchant_name IS NOT NULL)::INT) n_solo_dicc_rescata
  FROM tx t LEFT JOIN d USING (merchant_name) WHERE t.ttype='Purchase'""").to_string(index=False))

print("\n== A7 ¿merchant nulo es estructural? tasa de nulos por canal / estado / país / año (Purchase) ==")
for col in ["channel", "status", "country", "year(ts)", "currency"]:
    d = q(f"""SELECT {col} g, count(*) n, round(100*avg((merchant_name IS NULL)::INT),3) pct_merch_null,
               round(100*avg((mcat IS NULL)::INT),3) pct_mcat_null, round(100*avg((tcat IS NULL)::INT),3) pct_tcat_null
             FROM tx WHERE ttype='Purchase' GROUP BY 1 ORDER BY 1""")
    print(f"-- {col}: rango % merchant nulo {d.pct_merch_null.min()}–{d.pct_merch_null.max()} | mcat nulo {d.pct_mcat_null.min()}–{d.pct_mcat_null.max()} | tcat nulo {d.pct_tcat_null.min()}–{d.pct_tcat_null.max()}  (grupos={len(d)})")

print("\n== A8 ¿el comercio informa algo operativo? comercio x canal/estado/código (V de Cramér) ==")
def V(ct):
    ct = ct.values; chi2 = chi2_contingency(ct)[0]; n = ct.sum(); return np.sqrt(chi2/(n*(min(ct.shape)-1)))
for col in ["channel", "status", "coalesce(code,'NA')", "country", "currency"]:
    d = q(f"SELECT merchant_name, {col} g, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2")
    ct = d.pivot_table(index="merchant_name", columns="g", values="n", fill_value=0)
    print(f"V(comercio, {col}) = {V(ct):.4f}")
