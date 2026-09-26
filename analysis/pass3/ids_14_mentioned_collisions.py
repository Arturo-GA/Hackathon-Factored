# ids_14: cc.mentioned_products son IDs nuevos (no referencias). Las que existen en pr (0.65%) son colisiones de semilla:
# solo aparecen en la parte temprana del flujo de cc (donde el bucle de products, ~30M palabras, también pasó)
import sys, numpy as np, duckdb, collections
sys.path.insert(0, 'analysis/pass3')
con = duckdb.connect(); con.execute("SET memory_limit='600MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
B='data/bronze'
con.execute(f"""create temp table m as select file_row_number frn, trim(unnest(string_split(mentioned_products, ','))) pid
   from read_parquet('{B}/call_center_interactions.parquet', file_row_number=true) where mentioned_products is not null""")
con.execute(f"create temp table p as select product_id, file_row_number prn from read_parquet('{B}/products.parquet', file_row_number=true)")
print(con.execute("""select (frn*10 // 686296)::int dec_generacion, count(*) n, round(avg((p.product_id is not null)::int)*100,3) pct_existe, max(prn) max_fila_producto
   from m left join p on p.product_id=m.pid group by 1 order by 1""").fetchdf().to_string())
# posiciones en el flujo: primeras 3000 filas de cc
from ids_rng import words, chars_per_word, locate
c = chars_per_word(words(3_000_000))
rows = con.execute(f"select interaction_id, mentioned_products from read_parquet('{B}/call_center_interactions.parquet', file_row_number=true) where file_row_number<3000 order by file_row_number").fetchall()
offs=collections.Counter(); prev=0; nm=0
for iid, mp in rows:
    pp = locate(c, iid.split('-',1)[1], prev, prev+100000)
    if pp<0: continue
    prev=pp+1
    if mp is None: continue
    for x in mp.split(','):
        nm+=1; qq = locate(c, x.strip().split('-',1)[1], pp, pp+800)
        offs['found' if qq>=0 else 'nf']+=1
print('menciones en primeras 3000 filas cc:', nm, dict(offs))
