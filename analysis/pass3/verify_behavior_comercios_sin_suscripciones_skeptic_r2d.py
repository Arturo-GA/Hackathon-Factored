"""Verificador escéptico (ronda 2, parte D):
D1: ¿los comercios 'tipo suscripción' (Streaming Music, Internet Plus...) muestran exceso en 27-33 / 58-62 / 88-92 días?
    Test por comercio con TODOS los pares intra-producto (x en comercio m): P(y en m | ventana) vs P(y en m | resto).
D2: repetición j por comercio (obs vs esperado binomial) -> ¿algún comercio con cola pesada?
D3: tendencia de P(mismo comercio) con la brecha (deriva temporal de la mezcla).
D4: montos idénticos (arreglo del bug de pandas .eq)."""
import duckdb, pandas as pd, numpy as np
from scipy.stats import binom
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
SUBS = ('Cable TV', 'Streaming Music', 'Internet Plus', 'Empresa Telefónica', 'Servicios Públicos')

con.execute("""CREATE TEMP TABLE b AS SELECT product_id, merchant_name m, ts, amount a,
   row_number() OVER (PARTITION BY product_id ORDER BY ts, transaction_id) rn FROM tx WHERE merchant_name IS NOT NULL""")
W = """CASE WHEN d BETWEEN 27 AND 33 THEN 'w30' WHEN d BETWEEN 58 AND 62 THEN 'w60' WHEN d BETWEEN 88 AND 92 THEN 'w90'
           WHEN d BETWEEN 20 AND 26 OR d BETWEEN 34 AND 40 THEN 'vecinos30' ELSE 'resto' END"""
g = q(f"""WITH pr AS (SELECT x.m mx, (x.m=y.m) same, abs(date_diff('day', x.ts, y.ts)) d, (x.a=y.a) igual
                   FROM b x JOIN b y ON x.product_id=y.product_id AND x.rn<>y.rn)
          SELECT mx, {W} w, count(*) n, sum(same::INT) s, sum((same AND igual)::INT) s_igual, sum(igual::INT) igual FROM pr GROUP BY ALL""")
print("== D4 montos idénticos en pares intra-producto (ordenados en ambos sentidos) ==")
print(f"pares mismo comercio con monto idéntico: {int(g.s_igual.sum())} de {int(g.s.sum()):,}; cualquier par con monto idéntico: {int(g.igual.sum())} de {int(g.n.sum()):,}")

print("\n== D1 por comercio: P(y en m | ventana) / P(y en m | resto) ==")
t = g.pivot_table(index="mx", columns="w", values=["n", "s"], aggfunc="sum")
out = pd.DataFrame(index=t.index)
base_p = t["s"]["resto"] / t["n"]["resto"]
for w in ["w30", "w60", "w90", "vecinos30"]:
    pw = t["s"][w] / t["n"][w]
    out[f"RR_{w}"] = pw / base_p
    out[f"z_{w}"] = (t["s"][w] - t["n"][w] * base_p) / np.sqrt(t["n"][w] * base_p * (1 - base_p))
out["n_w30_pairs"] = t["n"]["w30"]
print(out.round(3).sort_values("z_w30", ascending=False).to_string())
grp = g.assign(tipo=np.where(g.mx.isin(SUBS), "suscripción-like", "resto")).groupby(["tipo", "w"])[["n", "s"]].sum()
grp["p"] = grp.s / grp.n
print("\nagrupado:"); print(grp.round(5).to_string())
for tipo in ["suscripción-like", "resto"]:
    gg = grp.loc[tipo]; pb = gg.loc["resto", "p"]
    for w in ["w30", "w60", "w90", "vecinos30"]:
        z = (gg.loc[w, "s"] - gg.loc[w, "n"] * pb) / np.sqrt(gg.loc[w, "n"] * pb * (1 - pb))
        print(f"{tipo:17s} {w:9s} RR={gg.loc[w,'p']/pb:.3f} z={z:.2f}")

print("\n== D2 repetición j por comercio: obs vs esperado binomial (dado k por producto y p_m global) ==")
freq = q("SELECT merchant_name m, count(*) n FROM tx WHERE merchant_name IS NOT NULL GROUP BY 1")
pm = dict(zip(freq.m, freq.n / freq.n.sum()))
kd = q("SELECT k, count(*) nent FROM (SELECT product_id, count(*) k FROM b GROUP BY 1) GROUP BY 1")
obs = q("SELECT m, c j, count(*) npairs FROM (SELECT product_id, m, count(*) c FROM b GROUP BY 1,2) GROUP BY 1,2")
rows = []
for m, p in pm.items():
    e2 = sum(ne * binom.sf(1, k, p) for k, ne in zip(kd.k, kd.nent))  # P(j>=2)
    e3 = sum(ne * binom.sf(2, k, p) for k, ne in zip(kd.k, kd.nent))  # P(j>=3)
    o = obs[obs.m == m]
    o2 = o[o.j >= 2].npairs.sum(); o3 = o[o.j >= 3].npairs.sum()
    rows.append((m, m in SUBS, o2, round(e2), round(o2 / e2, 3), o3, round(e3), round(o3 / e3, 3), int(o.j.max())))
r = pd.DataFrame(rows, columns=["comercio", "subs_like", "obs_j>=2", "esp_j>=2", "RR2", "obs_j>=3", "esp_j>=3", "RR3", "j_max"]).sort_values("RR3", ascending=False)
print(r.to_string(index=False))

print("\n== D3 P(mismo comercio) por brecha (todas las parejas intra-producto) ==")
print(q("""WITH pr AS (SELECT (x.m=y.m) same, date_diff('day', x.ts, y.ts) d FROM b x JOIN b y ON x.product_id=y.product_id AND x.rn<y.rn)
  SELECT CASE WHEN d<=30 THEN 'a_0-30' WHEN d<=90 THEN 'b_31-90' WHEN d<=180 THEN 'c_91-180' WHEN d<=365 THEN 'd_181-365' WHEN d<=730 THEN 'e_366-730' ELSE 'f_731+' END bin,
         count(*) n, round(avg(same::INT),5) p_same FROM pr GROUP BY 1 ORDER BY 1""").to_string(index=False))
