"""hunt_18: n_tx por cliente (R2=0.905 en hunt_04) lo explica solo el numero de productos Active. Caracteriza tx por producto activo."""
import duckdb
import numpy as np
import pandas as pd
pd.set_option('display.width', 220)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
df = con.execute("""WITH n AS (SELECT product_id, count(*) n FROM tx GROUP BY 1)
  SELECT p.ptype, count(*) prods, avg(coalesce(n.n,0)) mean_tx, stddev(coalesce(n.n,0)) sd_tx, min(coalesce(n.n,0)) mn, max(coalesce(n.n,0)) mx,
   quantile_cont(coalesce(n.n,0), [0.05,0.5,0.95]) q, corr(coalesce(n.n,0), date_diff('day', p.opened, DATE '2026-06-17')) r_age
  FROM pr p LEFT JOIN n USING (product_id) WHERE p.pstatus='Active' GROUP BY 1 ORDER BY 2 DESC""").df()
print(df.to_string())
c = con.execute("""SELECT c.customer_id, count(p.product_id) FILTER (WHERE p.pstatus='Active') n_active, (SELECT count(*) FROM tx t WHERE t.customer_id=c.customer_id) n_tx
  FROM cu c LEFT JOIN pr p USING (customer_id) GROUP BY 1""").df()
print('corr(n_active, n_tx)=', round(c[['n_active', 'n_tx']].corr().iloc[0, 1], 4), ' R2 lineal=', round(c[['n_active', 'n_tx']].corr().iloc[0, 1] ** 2, 4))
print(c.groupby('n_active').n_tx.agg(['size', 'mean', 'std', 'min', 'max']).round(2).head(10).to_string())
print('clientes sin producto Active con tx:', int(((c.n_active == 0) & (c.n_tx > 0)).sum()), ' con Active sin tx:', int(((c.n_active > 0) & (c.n_tx == 0)).sum()))
