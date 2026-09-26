"""Verificación independiente (parte 6): el título dice 'no existen cargos recurrentes'. ¿Hay recurrencia
mensual en OTROS tipos (Payment, Transfer, Withdrawal, Deposit...) sin comercio? Brechas entre tx
consecutivas del mismo ttype en el mismo producto vs nulo de permutación de ttype dentro del producto."""
import time
import duckdb
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

con = duckdb.connect("data/analysis.duckdb", read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

t0 = time.time()
con.execute("""CREATE TEMP TABLE b AS
  SELECT transaction_id, product_id, ts, amount, ttype,
         row_number() OVER (PARTITION BY product_id ORDER BY ts, transaction_id) rn_t
  FROM tx WHERE hash(product_id) % 4 = 0""")  # muestra de ~25% de productos (límite de RAM)
print(q("SELECT count(*) n_tx, count(DISTINCT product_id) n_prod FROM b"))
print(f"base creada en {time.time()-t0:.0f}s")

M = """WITH s AS (SELECT ttype, ts, amount, lag(ts) OVER w pts, lag(amount) OVER w pamt
      FROM {tab} WINDOW w AS (PARTITION BY product_id, ttype ORDER BY ts)),
  g AS (SELECT ttype, date_diff('day', pts, ts) gap, amount, pamt, ts, pts FROM s WHERE pts IS NOT NULL)
  SELECT ttype, count(*) n, median(gap) med_gap,
    sum((gap BETWEEN 27 AND 33)::INT) k27_33, sum((gap BETWEEN 28 AND 31)::INT) k28_31,
    sum((day(ts)=day(pts))::INT) k_dom, sum((abs(amount/nullif(pamt,0)-1)<=0.05)::INT) k_amt5,
    sum((gap BETWEEN 27 AND 33 AND abs(amount/nullif(pamt,0)-1)<=0.05)::INT) k_both
  FROM g GROUP BY 1"""
obs = q(M.format(tab="b")); obs["src"] = "obs"
res = [obs]
for i in range(4):
    t0 = time.time()
    con.execute(f"""CREATE OR REPLACE TEMP TABLE p AS
      WITH r AS (SELECT product_id, ttype, row_number() OVER (PARTITION BY product_id ORDER BY hash(transaction_id || 't{i}')) rn_r FROM b)
      SELECT a.product_id, a.ts, a.amount, r.ttype FROM b a JOIN r ON a.product_id=r.product_id AND a.rn_t=r.rn_r""")
    d = q(M.format(tab="p")); d["src"] = f"p{i}"
    res.append(d)
    con.execute("DROP TABLE p")
    print(f"perm {i} en {time.time()-t0:.0f}s")
allr = pd.concat(res)
o = obs.set_index("ttype")
nl = allr[allr.src != "obs"].groupby("ttype")[["n", "k27_33", "k28_31", "k_dom", "k_amt5", "k_both"]].sum()
out = pd.DataFrame({"n": o.n, "med_gap": o.med_gap})
for k in ["k27_33", "k28_31", "k_dom", "k_amt5", "k_both"]:
    out["p" + k[1:]] = o[k] / o.n
    out["p" + k[1:] + "_null"] = nl[k] / nl.n
    out["r" + k[1:]] = out["p" + k[1:]] / out["p" + k[1:] + "_null"]
print(out.round(4).T.to_string())
