"""Verificador escéptico (parte B): repetición cliente/producto-comercio vs azar (esperado analítico, no simulado)."""
import duckdb, pandas as pd, numpy as np
from scipy.stats import binom
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

freq = q("SELECT merchant_name, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1")
p = (freq.n / freq.n.sum()).values
print("sum p^2 (prob. de colisión iid) =", round(float((p**2).sum()), 5))

def expected_pairs(kdist, jmax=8):
    out = np.zeros(jmax + 1)
    for k, npr in zip(kdist.k.values, kdist.np.values):
        k = int(k)
        js = np.arange(1, jmax + 1)
        # E[#comercios con exactamente j compras] = sum_m Binom(k, p_m).pmf(j)
        e = binom.pmf(js[:, None], k, p[None, :]).sum(axis=1)
        out[1:] += npr * e
    return out

for level in ["product_id", "customer_id"]:
    obs = q(f"""WITH x AS (SELECT {level} id, merchant_name, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2)
                SELECT n j, count(*) npairs FROM x GROUP BY 1 ORDER BY 1""")
    kd = q(f"""SELECT k, count(*) np FROM (SELECT {level} id, count(*) k FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1) GROUP BY 1""")
    print(f"\n== {level}: #unidades={int(kd.np.sum()):,}  k medio={float((kd.k*kd.np).sum()/kd.np.sum()):.2f}  k max={int(kd.k.max())}")
    e = expected_pairs(kd)
    o = dict(zip(obs.j, obs.npairs))
    rows = []
    for j in range(1, 8):
        rows.append((j, int(o.get(j, 0)), round(e[j]), round(o.get(j, 0) / e[j], 4) if e[j] > 0 else None))
    print(pd.DataFrame(rows, columns=["j_compras_mismo_comercio", "observado", "esperado_iid", "obs/esp"]))
    # índice de repetición: pares (i<j) dentro de la unidad que comparten comercio vs esperado
    same = q(f"""WITH x AS (SELECT {level} id, merchant_name, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2)
                 SELECT sum(n*(n-1)/2) s FROM x""").s[0]
    allp = float((kd.np * kd.k * (kd.k - 1) / 2).sum())
    print(f"pares dentro de unidad: {allp:,.0f}; mismo comercio obs={same:,.0f} ({same/allp:.5f}) vs iid {float((p**2).sum()):.5f} -> razón {same/allp/float((p**2).sum()):.4f}")

# ¿la frecuencia de comercio cambia por país del cliente? (si sí, el modelo iid global estaría mal especificado)
print("\n== comercio x país (tx.country): V de Cramér ==")
ct = q("""SELECT country, merchant_name, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2""").pivot(index="merchant_name", columns="country", values="n").fillna(0)
from scipy.stats import chi2_contingency
chi2, pv, dof, _ = chi2_contingency(ct.values)
n = ct.values.sum(); V = np.sqrt(chi2 / (n * (min(ct.shape) - 1)))
print(f"V={V:.4f} chi2={chi2:.1f} dof={dof} p={pv:.3g}")
print((ct / ct.sum(axis=0)).round(4).head(24))
