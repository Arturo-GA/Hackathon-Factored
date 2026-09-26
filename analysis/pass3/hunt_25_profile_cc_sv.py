"""hunt_25: perfil rapido de columnas de cc, sv y cs (cardinalidad, nulos, valores) para barridos de V de Cramer.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/hunt_25_profile_cc_sv.py
"""
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='400MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'")
for tbl in ['cc', 'sv', 'cs']:
    n = con.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]
    print(f'===== {tbl} n={n}')
    for c, t, *_ in con.execute(f"DESCRIBE {tbl}").fetchall():
        if c.endswith('_id') or c in ('ts',):
            continue
        nn, nd = con.execute(f'SELECT count("{c}"), approx_count_distinct("{c}") FROM {tbl}').fetchone()
        s = f'{c:24s} {t:10s} null={1-nn/n:.3f} ndist~{nd}'
        if nd <= 12:
            vals = con.execute(f'SELECT "{c}", count(*) FROM {tbl} GROUP BY 1 ORDER BY 2 DESC').fetchall()
            s += ' ' + str([(str(v)[:30], k) for v, k in vals])
        elif t in ('DOUBLE', 'BIGINT', 'INTEGER', 'FLOAT'):
            mm = con.execute(f'SELECT min("{c}"), avg("{c}"), max("{c}") FROM {tbl}').fetchone()
            s += f' min={mm[0]} avg={mm[1]:.2f} max={mm[2]}'
        print(s, flush=True)
