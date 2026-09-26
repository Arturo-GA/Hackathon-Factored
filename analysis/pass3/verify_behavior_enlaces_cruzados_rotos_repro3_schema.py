"""Verificación (intento 3) behavior_enlaces_cruzados_rotos: exploración de formatos de IDs y tipos."""
import duckdb
import pandas as pd
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()
for t in ['pr', 'cc', 'de', 'cp', 'tx']:
    d = Q(f"DESCRIBE {t}")
    print(t, list(zip(d.column_name, d.column_type)))
print(Q("SELECT product_id, customer_id, product_number, ptype, currency FROM pr USING SAMPLE 5 ROWS"))
print(Q("SELECT customer_id, mentioned_products FROM cc WHERE mentioned_products IS NOT NULL USING SAMPLE 5 ROWS"))
print(Q("SELECT customer_id, product_id, event_type FROM de WHERE product_id IS NOT NULL USING SAMPLE 5 ROWS"))
print(Q("SELECT customer_id, affected_product_id, claimed, currency FROM cp WHERE claimed IS NOT NULL USING SAMPLE 5 ROWS"))
print(Q("SELECT length(product_id) l, count(*) n FROM pr GROUP BY 1 ORDER BY 1"))
print(Q("SELECT currency, count(*) n FROM pr GROUP BY 1 ORDER BY 1"))
