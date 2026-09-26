# ids_29: artefacto de "ensuciado": ¿hay una inyección de nulos ~5% MCAR en muchas columnas? tasa de nulos por columna (en la sub-población donde el campo aplica)
import duckdb
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf().to_string()
for t, where in [('cu',''),('pr',''),('ag',''),('br',''),('mc',''),('cp',"where status not in ('Open','Rejected')"),('cc',''),('sv',''),('tx',"where currency<>'USD'")]:
    samp = 'using sample 300000' if t in ('cc','sv','tx') else ''
    cols = [r[0] for r in con.execute(f"select column_name from information_schema.columns where table_name='{t}'").fetchall()]
    expr = ', '.join([f'round(avg(("{c}" is null)::int),4) "{c}"' for c in cols])
    r = con.execute(f"select {expr} from (select * from {t} {where} {samp})").fetchdf().T[0]
    near5 = r[(r>0.035)&(r<0.065)]
    print(t, 'cols=',len(cols), '| ~5% nulos:', near5.to_dict(), '| otros>0:', r[(r>0)&~((r>0.035)&(r<0.065))].to_dict())
