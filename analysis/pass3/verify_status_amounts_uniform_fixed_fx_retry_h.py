"""Verificacion (retry) status_amounts_uniform_fixed_fx. Parte H: amount_usd == round(amount/k, 2) (round de Python) en TODAS las filas no nulas (por lotes)."""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
kk = {'COP': 4000, 'ARS': 350}
cur = con.execute("select currency, amount, amount_usd from tx where amount_usd is not null")
tot = {'COP': [0, 0], 'ARS': [0, 0]}
while True:
    b = cur.fetchmany(200000)
    if not b: break
    for c, a, u in b:
        t = tot[c]; t[0] += 1; t[1] += (round(a / kk[c], 2) == u)
for c, (n, ok) in tot.items(): print(f"{c}: n={n} iguales a round(amount/{kk[c]},2) de Python = {ok} ({100*ok/n:.4f}%)")
