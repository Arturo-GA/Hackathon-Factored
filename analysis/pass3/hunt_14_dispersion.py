"""hunt_14: sobre-dispersion por cliente y por producto de rechazos, pendientes, reversos, fraude y fscore>=50
(test: varianza observada de conteos vs binomial con p global; y proporcion de clientes con >=k eventos vs esperado)."""
import duckdb
import numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
for lvl in ['customer_id', 'product_id']:
    df = con.execute(f"""SELECT count(*) n, count(*) FILTER (WHERE status='Declined') ndec, count(*) FILTER (WHERE status='Pending') pen,
        count(*) FILTER (WHERE status='Reversed') rev, count(*) FILTER (WHERE fraud) fr, count(*) FILTER (WHERE fscore>=50) fs50,
        count(*) FILTER (WHERE country IN ('USA','Spain','Brazil')) intl
        FROM tx GROUP BY {lvl}""").df()
    print(lvl, 'unidades', len(df))
    for c in ['ndec', 'pen', 'rev', 'fr', 'fs50', 'intl']:
        p = df[c].sum() / df.n.sum()
        exp_var = (df.n * p * (1 - p)).sum()
        obs_var = ((df[c] - df.n * p) ** 2).sum()
        # simulacion binomial para P(>=2) y P(>=3)
        rng = np.random.default_rng(0)
        sim = rng.binomial(df.n.values, p)
        print(f"  {c}: p={p:.4f} dispersion={obs_var/exp_var:.3f}  P(>=2) obs={np.mean(df[c]>=2):.4f} sim={np.mean(sim>=2):.4f}  P(>=3) obs={np.mean(df[c]>=3):.4f} sim={np.mean(sim>=3):.4f}")
