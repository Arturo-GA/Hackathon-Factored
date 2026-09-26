"""H22: techo de predictibilidad del volumen diario. Predictor = media entre semana / fin de semana (train: fechas < 2025-06-17).
Evalúa MAPE en test y si agregar volumen tx del mismo día o del día anterior mejora (R² del residuo)."""
import duckdb, pandas as pd, numpy as np
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
idx = pd.date_range('2023-06-17', '2026-06-17')
S = {}
for t in ['tx', 'cc', 'cp']:
    d = con.execute(f"SELECT process_date d, count(*) n FROM {t} GROUP BY 1").fetchdf(); d['d'] = pd.to_datetime(d.d)
    S[t] = d.set_index('d').n.reindex(idx, fill_value=0)
S = pd.DataFrame(S); S['we'] = S.index.dayofweek >= 5
tr = S.index < '2025-06-17'; te = ~tr
for t in ['tx', 'cc', 'cp']:
    m = S[tr].groupby('we')[t].mean(); pred = S.we.map(m)
    err = (S[t] - pred)/S[t]
    mape = err[te].abs().mean()
    # naive: mismo día semana anterior
    naive = S[t].shift(7); mape_naive = ((S[t]-naive)/S[t])[te].abs().mean()
    res = S[t]/pred - 1
    r_tx = res.corr(S['tx']/S.we.map(S[tr].groupby('we')['tx'].mean()) - 1) if t != 'tx' else np.nan
    print(f"{t}: media finde/semana MAPE test={mape:.4f} | naive t-7 MAPE={mape_naive:.4f} | MAPE teórico U(0.8,1.2)={np.abs(1-1/np.random.default_rng(0).uniform(0.8,1.2,10**6)).mean():.4f} | corr residuo con residuo tx mismo día={r_tx:.3f} | autocorr lag1={res.autocorr(1):.3f}")
