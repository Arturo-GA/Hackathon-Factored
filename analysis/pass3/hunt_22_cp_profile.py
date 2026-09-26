"""hunt_22: perfil de columnas de reclamos (cp) para barrido de reglas: cardinalidades, nulos y valores.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_22_cp_profile.py
"""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='300MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
cols = con.execute("DESCRIBE cp").fetchall()
n = con.execute("SELECT count(*) FROM cp").fetchone()[0]
print('n=', n)
for c, t, *_ in cols:
    nn, nd = con.execute(f'SELECT count("{c}"), count(DISTINCT "{c}") FROM cp').fetchone()
    s = f'{c:22s} {t:12s} null={1-nn/n:.3f} ndist={nd}'
    if nd <= 25:
        vals = con.execute(f'SELECT "{c}", count(*) FROM cp GROUP BY 1 ORDER BY 2 DESC').fetchall()
        s += ' ' + str([(v, k) for v, k in vals])
    else:
        mm = con.execute(f'SELECT min("{c}"), max("{c}") FROM cp').fetchone()
        s += f' min={mm[0]} max={mm[1]}'
    print(s)
