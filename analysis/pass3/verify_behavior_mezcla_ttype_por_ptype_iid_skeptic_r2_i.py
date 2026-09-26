"""Escéptico r2, I: ¿el 'iid' se extiende a montos? corr(log monto) entre tx consecutivas del mismo producto con el mismo ttype,
orden temporal vs orden barajado (1/8 de productos), DENTRO de moneda. Si ~0 en ambos: sin escala propia del producto ni memoria."""
import warnings; warnings.filterwarnings("ignore")
import duckdb, pandas as pd
pd.set_option("display.width", 230)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).df()
for lab, order in [('temporal', 't.ts, t.transaction_id'), ('barajado', "hash(t.transaction_id || 'am')")]:
    print(lab, q(f"""WITH z AS (SELECT t.currency, t.ttype, ln(t.amount) la, lag(ln(t.amount)) OVER w pla, lag(t.ttype) OVER w pt,
                 epoch(t.ts - lag(t.ts) OVER w)/86400.0 g
               FROM tx t WHERE hash(t.product_id) % 8 = 0 AND t.amount > 0
               WINDOW w AS (PARTITION BY t.product_id ORDER BY {order}))
             SELECT currency, ttype, count(*) n, round(corr(la, pla), 4) corr_mismo_tipo, round(corr(la, g), 4) corr_monto_gap
             FROM z WHERE pt = ttype GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False))
