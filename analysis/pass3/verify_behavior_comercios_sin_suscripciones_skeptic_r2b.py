"""Verificador escéptico (ronda 2, parte B): repetición entidad-comercio vs azar con esperanza EXACTA (binomial),
colas (j>=5, j máx) que delatarían suscripciones, y nivel cliente ENTRE productos distintos (preferencia de cliente)."""
import duckdb, pandas as pd, numpy as np
from scipy.stats import binom, poisson
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

freq = q("SELECT merchant_name, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1 ORDER BY 1")
p = (freq.n / freq.n.sum()).values
s2 = float((p**2).sum())
print(f"sum p^2 = {s2:.5f}  (1/24 = {1/24:.5f})")

def exp_counts(kd, jmax=40):
    out = np.zeros(jmax + 1)
    js = np.arange(1, jmax + 1)
    for k, nent in zip(kd.k.values.astype(int), kd.nent.values):
        out[1:] += nent * binom.pmf(js[:, None], k, p[None, :]).sum(axis=1)
    return out

for ent in ["product_id", "customer_id"]:
    kd = q(f"SELECT k, count(*) nent FROM (SELECT {ent}, count(*) k FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1) GROUP BY 1 ORDER BY 1")
    ob = q(f"""SELECT c j, count(*) npairs FROM (SELECT {ent}, merchant_name, count(*) c FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2) GROUP BY 1 ORDER BY 1""").set_index("j").npairs
    e = exp_counts(kd)
    print(f"\n== {ent}: entidades={kd.nent.sum():,}  k medio={np.average(kd.k, weights=kd.nent):.2f} k máx={kd.k.max()}  j máx observado={ob.index.max()}")
    rows = []
    for j in range(1, 8):
        o = int(ob.get(j, 0)); rows.append((str(j), o, round(e[j], 1), round(o / e[j], 4), round((o - e[j]) / np.sqrt(e[j]), 2)))
    for lo in [5, 8, 10]:
        o = int(ob[ob.index >= lo].sum()); ee = e[lo:].sum()
        rows.append((f">={lo}", o, round(ee, 2), round(o / ee, 4) if ee > 0 else np.nan, round((o - ee) / np.sqrt(ee), 2) if ee > 0 else np.nan))
    print(pd.DataFrame(rows, columns=["j", "obs", "esp_iid", "obs/esp", "z_pois"]).to_string(index=False))
    same = q(f"SELECT sum(c*(c-1)/2) s FROM (SELECT {ent}, merchant_name, count(*) c FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2)").s[0]
    allp = float((kd.nent * kd.k * (kd.k - 1) / 2).sum())
    print(f"pares intra-{ent}: {allp:,.0f}; P(mismo comercio) obs={same/allp:.5f} vs iid {s2:.5f} -> razón {same/allp/s2:.4f}")

print("\n== Nivel cliente ENTRE productos distintos del mismo cliente: P(mismo comercio) vs sum p^2 ==")
print(q(f"""WITH b AS (SELECT customer_id, product_id, merchant_name m FROM tx WHERE merchant_name IS NOT NULL),
  cp AS (SELECT customer_id, product_id, m, count(*) c FROM b GROUP BY 1,2,3),
  cpt AS (SELECT customer_id, product_id, sum(c) k FROM cp GROUP BY 1,2),
  -- pares entre productos distintos: total = sum_{{a<b}} k_a k_b ; mismo comercio = sum_m sum_{{a<b}} c_am c_bm
  tot AS (SELECT customer_id, (sum(k)*sum(k) - sum(k*k))/2 pairs FROM cpt GROUP BY 1),
  sm AS (SELECT customer_id, m, (sum(c)*sum(c) - sum(c*c))/2 sp FROM cp GROUP BY 1,2)
  SELECT (SELECT sum(pairs) FROM tot) pares_entre_productos, (SELECT sum(sp) FROM sm) mismo_comercio,
         (SELECT sum(sp) FROM sm)/(SELECT sum(pairs) FROM tot) p_obs, {s2} p_iid,
         (SELECT sum(sp) FROM sm)/(SELECT sum(pairs) FROM tot)/{s2} razon""").to_string(index=False))

print("\n== ¿La mezcla de comercios varía por segmento/ptype/año/país? (si sí, el nulo iid global estaría mal especificado) ==")
from scipy.stats import chi2_contingency
def V(d):
    ct = d.pivot_table(index="merchant_name", columns="g", values="n", fill_value=0).values
    chi2 = chi2_contingency(ct)[0]; n = ct.sum(); return np.sqrt(chi2/(n*(min(ct.shape)-1)))
for expr, frm in [("pr.ptype", "tx JOIN pr USING(product_id)"), ("cu.segment", "tx JOIN cu USING(customer_id)"),
                  ("year(tx.ts)", "tx"), ("tx.country", "tx"), ("cu.gender", "tx JOIN cu USING(customer_id)")]:
    d = q(f"SELECT tx.merchant_name, {expr} g, count(*) n FROM {frm} WHERE tx.merchant_name IS NOT NULL GROUP BY 1,2")
    print(f"V(comercio, {expr}) = {V(d):.4f}  (grupos={d.g.nunique()})")
