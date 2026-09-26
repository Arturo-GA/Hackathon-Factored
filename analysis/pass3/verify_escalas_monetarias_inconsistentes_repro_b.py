import duckdb, numpy as np, pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
def q(s, title=None):
    if title: print('==', title)
    print(con.execute(s).df().to_string(), '\n')
# 5. cp.claimed por moneda
q("""select currency, count(*) n, count(claimed) n_claimed, min(claimed) mn, quantile_cont(claimed,0.25) p25, median(claimed) med,
   quantile_cont(claimed,0.75) p75, max(claimed) mx from cp group by 1 order by 1""", "claimed por moneda")
q("""select case_type, count(*) n, count(claimed) n_claimed, round(avg((claimed is not null)::int),3) pct from cp group by 1 order by 2 desc""", "claimed por case_type")
# uniformidad: histograma en 10 bins de 50-5000
q("""select floor((claimed-50)/495) bin, count(*) n from cp where claimed is not null group by 1 order by 1""", "hist claimed")
# moneda del reclamo vs pais del cliente
q("""select cu.country, cp.currency, count(*) n from cp join cu using(customer_id) where cp.claimed is not null group by all order by 1,2""", "moneda reclamo vs pais cliente (con claimed)")
q("""select cu.country, cp.currency, count(*) n from cp join cu using(customer_id) group by all order by 1,2""", "moneda reclamo vs pais cliente (todos)")
# moneda del reclamo vs moneda del producto afectado
q("""select cp.currency cpcur, p.currency pcur, count(*) n from cp left join pr p on p.product_id=cp.affected_product_id group by all order by 1,2""", "moneda reclamo vs producto afectado")
