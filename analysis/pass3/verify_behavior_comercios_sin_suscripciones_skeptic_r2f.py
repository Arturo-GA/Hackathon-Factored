"""Verificador escéptico (ronda 2, parte F): ¿tcat en Payment significa algo? (tcat x ptype) y ¿el comercio explica el monto?"""
import duckdb, pandas as pd, numpy as np
from scipy.stats import chi2_contingency
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
d = q("SELECT p.ptype, t.tcat, count(*) n FROM tx t JOIN pr p USING(product_id) WHERE t.ttype='Payment' AND t.tcat IS NOT NULL GROUP BY 1,2")
ct = d.pivot_table(index="ptype", columns="tcat", values="n", fill_value=0)
print((100 * ct.div(ct.sum(1), axis=0)).round(1).to_string())
chi2 = chi2_contingency(ct.values)[0]; N = ct.values.sum()
print(f"V(ptype, tcat | Payment) = {np.sqrt(chi2/(N*(min(ct.shape)-1))):.4f}  N={N:,}")
print(q("""WITH b AS (SELECT currency, merchant_name g, ln(amount) la FROM tx WHERE merchant_name IS NOT NULL AND amount>0),
  gg AS (SELECT currency, g, count(*) n, avg(la) m FROM b GROUP BY 1,2), c AS (SELECT currency, avg(la) mc, var_pop(la) vc, count(*) nc FROM b GROUP BY 1)
  SELECT c.currency, c.nc n, round(sum(gg.n*(gg.m-c.mc)^2)/(c.vc*c.nc),5) r2_logmonto_por_comercio FROM gg JOIN c USING(currency) GROUP BY c.currency, c.nc, c.vc""").to_string(index=False))
