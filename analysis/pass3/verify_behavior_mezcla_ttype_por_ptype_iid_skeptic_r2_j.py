"""Escéptico r2, J: lift pooled Adjustment->Adjustment a nivel producto (¿=10 por pura composición?) y reglas de nulos que
co-varían con ttype (merchant/mcat/tcat) para extender el guardrail."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
print(q("""WITH s AS (SELECT t.ttype, lag(t.ttype) OVER (PARTITION BY t.product_id ORDER BY t.ts, t.transaction_id) prev FROM tx t)
           SELECT avg((ttype='Adjustment')::INT) FILTER (WHERE prev='Adjustment') p_adj_dado_adj, avg((ttype='Adjustment')::INT) p_adj,
                  avg((ttype='Adjustment')::INT) FILTER (WHERE prev='Adjustment') / avg((ttype='Adjustment')::INT) lift FROM s WHERE prev IS NOT NULL""").to_string(index=False))
print(q("""SELECT (merchant_name IS NOT NULL) con_comercio, (mcat IS NOT NULL) con_mcat, (tcat IS NOT NULL) con_tcat, ttype, count(*) n
           FROM tx GROUP BY ALL ORDER BY 1,2,3,4""").to_string(index=False))
