"""Verificación independiente (parte 2): forma de last_tx y last_updated, R2 multivariable de bal, Spearman sin Seguro."""
import duckdb
import numpy as np
import pandas as pd
from scipy import stats

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")


def Q(s):
    return con.execute(s).df()


# last_tx ~ U(opened, fin)?
u = Q("""SELECT date_diff('second', opened::TIMESTAMP, last_tx)*1.0 / date_diff('second', opened::TIMESTAMP, TIMESTAMP '2026-06-18') u
         FROM pr WHERE last_tx IS NOT NULL AND opened < DATE '2026-06-17' USING SAMPLE 100000 ROWS""")['u'].values
print("last_tx posición relativa en [opened, fin]: cuantiles", np.round(np.quantile(u, [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]), 3),
      "min/max", round(u.min(), 4), round(u.max(), 4))
print("KS vs U(0,1):", stats.kstest(u, 'uniform'))

# last_updated relativo a opened
print(Q("""SELECT quantile_cont(date_diff('day', opened, last_updated::DATE), [0, 0.01, 0.25, 0.5, 0.75, 0.99, 1]) d_open_upd,
          avg((last_updated::DATE >= opened)::INT) upd_ge_open FROM pr"""))

# Seguro: bal constante?
print(Q("SELECT ptype, min(bal), max(bal), count(DISTINCT bal) nd FROM pr WHERE ptype='Seguro' GROUP BY 1"))

# Spearman sin grupos constantes
con.execute("""CREATE TEMP TABLE agg AS SELECT product_id, count(*) ntx,
  sum(CASE WHEN ttype='Deposit' THEN amount ELSE 0 END) dep,
  sum(CASE WHEN ttype IN ('Withdrawal','Purchase','Payment','Transfer') THEN amount ELSE 0 END) outf,
  sum(CASE WHEN status='Approved' AND ttype='Deposit' THEN amount ELSE 0 END) dep_ok,
  sum(CASE WHEN status='Approved' AND ttype IN ('Withdrawal','Purchase','Payment','Transfer') THEN amount ELSE 0 END) out_ok,
  sum(CASE WHEN ttype='Purchase' THEN amount ELSE 0 END) pur, sum(CASE WHEN ttype='Payment' THEN amount ELSE 0 END) pay,
  sum(CASE WHEN ttype='Withdrawal' THEN amount ELSE 0 END) wd, sum(CASE WHEN ttype='Transfer' THEN amount ELSE 0 END) trf,
  sum(CASE WHEN ttype='Adjustment' THEN amount ELSE 0 END) adj
  FROM tx GROUP BY 1""")
print(Q("""WITH x AS (SELECT p.ptype, p.currency, rank() OVER (PARTITION BY p.ptype, p.currency ORDER BY p.bal) rb,
            rank() OVER (PARTITION BY p.ptype, p.currency ORDER BY a.dep_ok-a.out_ok) rn FROM pr p JOIN agg a USING(product_id) WHERE p.ptype<>'Seguro')
   SELECT count(*) ncombos, min(s) min_spearman, max(s) max_spearman FROM (SELECT ptype, currency, corr(rb, rn) s FROM x GROUP BY 1,2)"""))

# R2 multivariable (OLS con intercepto) de bal ~ flujos por tipo de tx, por ptype x moneda
rows = []
for ptype in [r[0] for r in con.execute("SELECT DISTINCT ptype FROM pr WHERE ptype<>'Seguro'").fetchall()]:
    d = Q(f"""SELECT p.currency, p.bal, a.dep, a.pur, a.pay, a.wd, a.trf, a.adj, a.ntx, a.dep_ok-a.out_ok net_ok
              FROM pr p JOIN agg a USING(product_id) WHERE p.ptype='{ptype}'""")
    for ccy, g in d.groupby('currency'):
        X = g[['dep', 'pur', 'pay', 'wd', 'trf', 'adj', 'ntx', 'net_ok']].values
        X = X[:, X.std(0) > 0]
        X = np.column_stack([np.ones(len(X)), X])
        y = g['bal'].values
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        r2 = 1 - ((y - X @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        rows.append((ptype, ccy, len(g), round(r2, 5)))
r = pd.DataFrame(rows, columns=['ptype', 'ccy', 'n', 'r2_in_sample'])
print(r.to_string())
print("R2 max:", r.r2_in_sample.max())
