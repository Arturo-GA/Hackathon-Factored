"""Sonda rápida (verificador, intento 2): rangos de fechas, días extremos y desfase ts - process_date por tabla."""
import duckdb, pandas as pd
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
for t in ['tx', 'cc', 'cp', 'sv']:
    r = con.execute(f"""SELECT count(*) n, min(process_date) pmin, max(process_date) pmax, count(DISTINCT process_date) ndays,
        min(ts) tsmin, max(ts) tsmax,
        min(epoch(ts) - epoch(process_date::TIMESTAMP))/3600 off_min_h, max(epoch(ts) - epoch(process_date::TIMESTAMP))/3600 off_max_h,
        avg((CAST(ts AS DATE) <> process_date)::INT) frac_tsdate_ne_pd, avg((CAST(ts AS DATE) = process_date + 1)::INT) frac_next,
        count(*) FILTER (WHERE process_date IS NULL) n_null_pd, count(*) FILTER (WHERE ts IS NULL) n_null_ts
        FROM {t}""").fetchdf()
    print(t); print(r.T.to_string())
    e = con.execute(f"""WITH d AS (SELECT process_date d, count(*) n FROM {t} GROUP BY 1)
        SELECT * FROM d WHERE d IN (SELECT min(d) FROM d) OR d IN (SELECT max(d) FROM d) OR d <= DATE '2023-06-19' OR d >= DATE '2026-06-15' ORDER BY d""").fetchdf()
    print(e.to_string(index=False))
for t in ['de', 'cs']:
    print(t, con.execute(f"SELECT min(ts), max(ts), count(DISTINCT CAST(ts AS DATE)) FROM {t}").fetchall())
print(con.execute("SELECT column_name FROM information_schema.columns WHERE table_name='de'").fetchdf().column_name.tolist())
