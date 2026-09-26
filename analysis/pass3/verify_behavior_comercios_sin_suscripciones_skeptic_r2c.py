"""Verificador escéptico (ronda 2, parte C): periodicidad y montos.
C1: TODOS los pares de compras del mismo producto -> P(mismo comercio | brecha d). Si hubiera suscripciones, P subiría en d≈30,60,90.
C2: la comparación del hallazgo (consecutivas mismo comercio vs 'compras cualesquiera') frente a un nulo de permutación.
"""
import duckdb, pandas as pd, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

con.execute("""CREATE TEMP TABLE b AS SELECT product_id, merchant_name m, ts, amount a,
   row_number() OVER (PARTITION BY product_id ORDER BY ts, transaction_id) rn, transaction_id tid
   FROM tx WHERE merchant_name IS NOT NULL""")

print("== C1 pares intra-producto: P(mismo comercio | brecha en días) ==")
g = q("""SELECT date_diff('day', x.ts, y.ts) d, (x.m=y.m) same, day(x.ts)=day(y.ts) dom,
            abs(y.a/x.a-1)<=0.05 amt5, x.a=y.a eq, count(*) n
         FROM b x JOIN b y ON x.product_id=y.product_id AND x.rn<y.rn GROUP BY ALL""")
N = g.n.sum(); S = g[g.same].n.sum(); p0 = S / N
print(f"pares={N:,}  mismo comercio={S:,}  P={p0:.5f}")
byd = g.groupby("d").apply(lambda t: pd.Series({"n": t.n.sum(), "s": t[t.same].n.sum()}), include_groups=False)
byd["p"] = byd.s / byd.n; byd["z"] = (byd.s - byd.n * p0) / np.sqrt(byd.n * p0 * (1 - p0))
sel = byd.loc[[d for d in [0, 1, 7, 14, 28, 29, 30, 31, 59, 60, 61, 90, 91, 364, 365, 366] if d in byd.index]]
print(sel.round(4).to_string())
r = byd[(byd.index >= 1) & (byd.index <= 400)]
print(f"d=1..400: max|z|={r.z.abs().max():.2f} en d={int(r.z.abs().idxmax())}; #|z|>3.3 (Bonf. ~400 tests a 0.05/400≈3.5)= {(r.z.abs()>3.5).sum()}")
def win(lo, hi):
    t = byd[(byd.index >= lo) & (byd.index <= hi)]; return t.s.sum() / t.n.sum(), t.n.sum()
for lo, hi in [(27, 33), (28, 31), (58, 62), (88, 92), (6, 8), (13, 15), (360, 370)]:
    pw, nw = win(lo, hi); print(f"ventana {lo}-{hi}: P(mismo)={pw:.5f} razón vs global {pw/p0:.3f} (n={nw:,})")
# mismo día del mes (con brecha >=27) y montos
t = g[g.d >= 27]
for lab, msk in [("mismo día-del-mes (d>=27)", t.dom), ("distinto día-del-mes (d>=27)", ~t.dom)]:
    tt = t[msk]; print(f"{lab}: P(mismo comercio)={tt[tt.same].n.sum()/tt.n.sum():.5f} (n={tt.n.sum():,})")
for lab, msk in [("monto a ±5%", g.amt5), ("monto >5% distinto", ~g.amt5), ("monto idéntico", g.eq)]:
    tt = g[msk]; print(f"{lab}: P(mismo comercio)={tt[tt.same].n.sum()/tt.n.sum():.5f} (n={tt.n.sum():,})")
for lab, msk in [("mismo comercio", g.same), ("distinto comercio", ~g.same)]:
    tt = g[msk]; print(f"{lab}: %monto±5%={100*tt[tt.amt5].n.sum()/tt.n.sum():.3f}  %monto idéntico={100*tt[tt.eq].n.sum()/tt.n.sum():.4f}  %brecha27-33={100*tt[(tt.d>=27)&(tt.d<=33)].n.sum()/tt.n.sum():.3f}")

print("\n== C2 métrica del hallazgo (consecutivas mismo producto-comercio) vs nulo de permutación (3 semillas) ==")
MET = """WITH s AS (SELECT m, ts, a, lag(ts) OVER w pts, lag(a) OVER w pa FROM {t} WINDOW w AS (PARTITION BY product_id, m ORDER BY ts))
  SELECT m, count(*) n, median(date_diff('day', pts, ts)) med_gap,
    avg((date_diff('day', pts, ts) BETWEEN 27 AND 33)::INT) p27_33, avg((abs(a/pa-1)<0.05)::INT) p_amt5
  FROM s WHERE pts IS NOT NULL GROUP BY 1"""
obs = q(MET.format(t="b"))
res = []
for sd in ["x1", "x2", "x3"]:
    con.execute(f"""CREATE OR REPLACE TEMP TABLE pm AS WITH r AS (SELECT product_id, m, row_number() OVER (PARTITION BY product_id ORDER BY md5(tid || '{sd}')) rr FROM b)
       SELECT b.product_id, b.ts, b.a, r.m FROM b JOIN r ON b.product_id=r.product_id AND b.rn=r.rr""")
    res.append(q(MET.format(t="pm")).assign(seed=sd))
nul = pd.concat(res)
def tot(d):
    w = d.n.sum(); return pd.Series({"n": w, "p27_33": (d.p27_33 * d.n).sum() / w, "p_amt5": (d.p_amt5 * d.n).sum() / w})
print("observado:", tot(obs).round(5).to_dict())
print("permutado (media 3 semillas):", nul.groupby("seed").apply(tot, include_groups=False).mean().round(5).to_dict())
print(f"rango por comercio observado: med_gap {obs.med_gap.min()}–{obs.med_gap.max()} | p27_33 {100*obs.p27_33.min():.2f}–{100*obs.p27_33.max():.2f}% | p_amt5 {100*obs.p_amt5.min():.2f}–{100*obs.p_amt5.max():.2f}%")
nm = nul.groupby("m").apply(lambda d: pd.Series({"p27_33_null": (d.p27_33*d.n).sum()/d.n.sum(), "med_gap_null": d.med_gap.mean()}), include_groups=False)
j = obs.set_index("m").join(nm)
print(f"rango por comercio permutado: p27_33 {100*j.p27_33_null.min():.2f}–{100*j.p27_33_null.max():.2f}% | med_gap {j.med_gap_null.min():.0f}–{j.med_gap_null.max():.0f}")
print(j.loc[[x for x in ["Cable TV", "Streaming Music", "Internet Plus", "Empresa Telefónica", "Servicios Públicos"]], ["n", "med_gap", "med_gap_null", "p27_33", "p27_33_null", "p_amt5"]].round(4).to_string())
print("\nbaseline del hallazgo: consecutivas de compras del producto (cualquier comercio):")
print(q("""WITH s AS (SELECT ts, amount, lag(ts) OVER w pts, lag(amount) OVER w pa FROM tx WHERE ttype='Purchase' WINDOW w AS (PARTITION BY product_id ORDER BY ts))
  SELECT count(*) n, median(date_diff('day', pts, ts)) med_gap, avg((date_diff('day', pts, ts) BETWEEN 27 AND 33)::INT) p27_33, avg((abs(amount/pa-1)<0.05)::INT) p_amt5
  FROM s WHERE pts IS NOT NULL""").round(5).to_string(index=False))
