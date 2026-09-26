"""Verificación independiente (parte 4): el pequeño exceso de brechas 27-33 d (razón 1.05, z~2.7)
¿es periodicidad mensual o un exceso general de brechas cortas? Histograma de brechas observado vs
8 permutaciones dentro de producto; foco en los 2 comercios con |z|>3 y en los de tipo suscripción."""
import duckdb
import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 200)

con = duckdb.connect("data/analysis.duckdb", read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()

con.execute("""CREATE TEMP TABLE base AS
  SELECT transaction_id, product_id, ts, amount, merchant_name,
         row_number() OVER (PARTITION BY product_id ORDER BY ts, transaction_id) rn_t
  FROM tx WHERE merchant_name IS NOT NULL""")

BINS = """CASE WHEN gap=0 THEN 'a_0' WHEN gap<=6 THEN 'b_1-6' WHEN gap<=13 THEN 'c_7-13' WHEN gap<=20 THEN 'd_14-20'
  WHEN gap<=26 THEN 'e_21-26' WHEN gap<=33 THEN 'f_27-33' WHEN gap<=40 THEN 'g_34-40' WHEN gap<=60 THEN 'h_41-60'
  WHEN gap<=90 THEN 'i_61-90' WHEN gap<=180 THEN 'j_91-180' WHEN gap<=365 THEN 'k_181-365' ELSE 'l_366+' END"""
HIST = """WITH s AS (SELECT merchant_name, ts, lag(ts) OVER (PARTITION BY product_id, merchant_name ORDER BY ts) pts FROM {tab}),
  g AS (SELECT merchant_name, date_diff('day', pts, ts) gap FROM s WHERE pts IS NOT NULL)
  SELECT merchant_name IN ('Estación de Servicio','Óptica Visión') flagged,
         merchant_name IN ('Cable TV','Streaming Music','Internet Plus','Empresa Telefónica','Servicios Públicos') subs_like,
         {bins} bin, count(*) n FROM g GROUP BY ALL"""

obs = q(HIST.format(tab="base", bins=BINS)); obs["src"] = "obs"
res = [obs]
for i in range(8):
    con.execute(f"""CREATE OR REPLACE TEMP TABLE perm AS
      WITH r AS (SELECT product_id, merchant_name,
                  row_number() OVER (PARTITION BY product_id ORDER BY hash(transaction_id || 'h{i}')) rn_r FROM base)
      SELECT a.product_id, a.ts, r.merchant_name FROM base a JOIN r ON a.product_id=r.product_id AND a.rn_t=r.rn_r""")
    d = q(HIST.format(tab="perm", bins=BINS)); d["src"] = f"p{i}"
    res.append(d)
    con.execute("DROP TABLE perm")
allr = pd.concat(res)


def table(df, title):
    t = df.groupby(["src", "bin"]).n.sum().unstack("src").fillna(0)
    nulls = t.drop(columns="obs")
    out = pd.DataFrame({"obs": t.obs, "null_mean": nulls.mean(axis=1), "null_sd": nulls.std(axis=1, ddof=1)})
    out["ratio"] = out.obs / out.null_mean
    out["z_perm"] = (out.obs - out.null_mean) / out.null_sd
    out["z_pois"] = (out.obs - out.null_mean) / np.sqrt(out.null_mean)
    print(f"\n== {title} (n pares={int(t.obs.sum()):,}) ==")
    print(out.round(3).to_string())


table(allr, "Todas las compras repetidas al mismo comercio")
table(allr[allr.flagged], "Estación de Servicio + Óptica Visión")
table(allr[allr.subs_like], "Comercios tipo suscripción/servicio (Cable TV, Streaming, Internet, Telefónica, Serv. Públicos)")
table(allr[~allr.flagged], "Todos menos los 2 marcados")
