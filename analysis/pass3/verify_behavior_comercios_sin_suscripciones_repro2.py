"""Verificación independiente (parte 2): repetición producto/cliente-comercio vs azar (esperanza
multinomial EXACTA, no simulación) y regularidad temporal/montos vs un nulo de permutación de
etiquetas de comercio dentro del producto (conserva tiempos, montos y la mezcla de comercios del producto)."""
import duckdb
import numpy as np
import pandas as pd
from scipy.stats import binom

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 200)

con = duckdb.connect("data/analysis.duckdb", read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

freq = q("SELECT merchant_name, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1")
p = (freq.n / freq.n.sum()).values


def expected_pairs(kdist, p, jmax=8):
    """E[# pares entidad-comercio con exactamente j compras] si cada compra elige comercio iid ~ p."""
    out = np.zeros(jmax + 1)
    for k, nent in zip(kdist.k.values, kdist.nent.values):
        for j in range(1, min(k, jmax) + 1):
            out[j] += nent * binom.pmf(j, k, p).sum()
    return out


for ent in ["product_id", "customer_id"]:
    print(f"\n== Repetición {ent}-comercio: observado vs esperado (multinomial exacto, p global) ==")
    obs = q(f"""WITH pr AS (SELECT {ent}, merchant_name, count(*) c FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1,2)
               SELECT c j, count(*) npairs FROM pr GROUP BY 1 ORDER BY 1""")
    kd = q(f"""SELECT k, count(*) nent FROM (SELECT {ent}, count(*) k FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1) GROUP BY 1 ORDER BY 1""")
    print(f"entidades={kd.nent.sum():,}  k medio={np.average(kd.k, weights=kd.nent):.3f}  k max={kd.k.max()}")
    e = expected_pairs(kd, p)
    obs = obs.set_index("j").npairs
    rows = []
    for j in range(1, 9):
        o = int(obs.get(j, 0))
        rows.append((j, o, round(e[j], 1), round(o / e[j], 4) if e[j] > 0 else np.nan))
    tail_o = int(obs[obs.index >= 5].sum())
    rows.append(("≥5", tail_o, round(e[5:].sum(), 1), round(tail_o / e[5:].sum(), 4) if e[5:].sum() > 0 else np.nan))
    print(pd.DataFrame(rows, columns=["j", "obs", "esperado", "obs/esp"]).to_string(index=False))
    # compras "repetidas" = compras que no son la primera al comercio en esa entidad
    rep_o = int(((obs.index.values - 1) * obs.values).sum())
    rep_e = float(sum((j - 1) * e[j] for j in range(1, 9)))
    print(f"compras repetidas (c-1 sumado): obs={rep_o:,} esp={rep_e:,.0f} razón={rep_o/rep_e:.4f}")

# ----- Regularidad temporal y montos -----
print("\n== Brechas entre compras consecutivas al mismo comercio (mismo producto): observado vs permutación ==")
con.execute("""CREATE TEMP TABLE base AS
  SELECT transaction_id, product_id, ts, amount, merchant_name,
         row_number() OVER (PARTITION BY product_id ORDER BY ts, transaction_id) rn_t,
         row_number() OVER (PARTITION BY product_id ORDER BY hash(transaction_id || 'seed_v1')) rn_r
  FROM tx WHERE merchant_name IS NOT NULL""")
con.execute("""CREATE TEMP TABLE perm AS
  SELECT a.product_id, a.ts, a.amount, b.merchant_name AS merchant_name
  FROM base a JOIN base b ON a.product_id=b.product_id AND a.rn_t=b.rn_r""")
print(q("SELECT (SELECT count(*) FROM base) n_base, (SELECT count(*) FROM perm) n_perm"))

GAPS = """WITH s AS (SELECT merchant_name, ts, amount,
        lag(ts) OVER (PARTITION BY product_id, merchant_name ORDER BY ts) pts,
        lag(amount) OVER (PARTITION BY product_id, merchant_name ORDER BY ts) pamt
      FROM {tab}), g AS (SELECT merchant_name, date_diff('day', pts, ts) gap, amount, pamt, ts, pts FROM s WHERE pts IS NOT NULL)
  SELECT {grp} count(*) n, median(gap) med_gap,
    avg((gap BETWEEN 27 AND 33)::INT) p27_33,
    avg((gap BETWEEN 28 AND 31)::INT) p28_31,
    avg((gap BETWEEN 6 AND 8)::INT) p6_8,
    avg((day(ts)=day(pts))::INT) p_same_dom,
    avg((abs(amount/pamt-1)<=0.05)::INT) p_amt5,
    avg((amount=pamt)::INT) p_amt_eq,
    avg((abs(amount/pamt-1)<=0.05 AND gap BETWEEN 27 AND 33)::INT) p_both
  FROM g {gb}"""
tot_o = q(GAPS.format(tab="base", grp="", gb=""))
tot_p = q(GAPS.format(tab="perm", grp="", gb=""))
t = pd.concat([tot_o.assign(src="observado"), tot_p.assign(src="permutado")]).set_index("src")
print(t.round(5).to_string())

per = q(GAPS.format(tab="base", grp="merchant_name,", gb="GROUP BY 1 ORDER BY 1"))
perp = q(GAPS.format(tab="perm", grp="merchant_name,", gb="GROUP BY 1 ORDER BY 1"))
per = per.merge(perp[["merchant_name", "p27_33", "p_amt5", "p_same_dom"]], on="merchant_name", suffixes=("", "_perm"))
print(per.round(4).to_string(index=False))
print("rango med_gap: %s–%s | p27_33: %.4f–%.4f | p_amt5: %.4f–%.4f" % (per.med_gap.min(), per.med_gap.max(),
      per.p27_33.min(), per.p27_33.max(), per.p_amt5.min(), per.p_amt5.max()))

print("\n== Línea base del hallazgo: compras consecutivas del producto (cualquier comercio, ttype=Purchase) ==")
print(q("""WITH s AS (SELECT product_id, ts, amount, lag(ts) OVER (PARTITION BY product_id ORDER BY ts) pts,
               lag(amount) OVER (PARTITION BY product_id ORDER BY ts) pamt FROM tx WHERE ttype='Purchase')
         SELECT count(*) n, median(date_diff('day', pts, ts)) med_gap, avg((date_diff('day', pts, ts) BETWEEN 27 AND 33)::INT) p27_33,
                avg((abs(amount/pamt-1)<=0.05)::INT) p_amt5 FROM s WHERE pts IS NOT NULL""").round(4).to_string(index=False))
