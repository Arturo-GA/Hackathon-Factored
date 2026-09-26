"""H14: patrón temporal tx vs call center (cc) vs digital (de) vs reclamos (cp) vs campañas (cs):
perfil semanal, multiplicador diario (sd de residuo, ¿uniforme?), correlación diaria entre tablas, perfil horario."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
idx = pd.date_range('2023-06-17', '2026-06-17')
src = {
 'tx': "SELECT process_date d, count(*) n FROM tx GROUP BY 1",
 'cc': "SELECT process_date d, count(*) n FROM cc GROUP BY 1",
 'cp': "SELECT process_date d, count(*) n FROM cp GROUP BY 1",
 'sv': "SELECT process_date d, count(*) n FROM sv GROUP BY 1",
 'de': "SELECT CAST(ts AS DATE) d, count(*) n FROM de GROUP BY 1",
 'de_cust': "SELECT CAST(ts AS DATE) d, count(*) n FROM de WHERE customer_id IS NOT NULL GROUP BY 1",
 'de_sess': "SELECT CAST(ts AS DATE) d, count(DISTINCT session_id) n FROM de GROUP BY 1",
 'cs': "SELECT CAST(ts AS DATE) d, count(*) n FROM cs GROUP BY 1",
}
S = {}
for k, q in src.items():
    d = con.execute(q).fetchdf(); d['d'] = pd.to_datetime(d.d)
    S[k] = d.set_index('d').n.reindex(idx, fill_value=0)
S = pd.DataFrame(S)
dw = S.index.dayofweek
print("perfil semanal (0=lun) relativo a media:"); print((S.groupby(dw).mean()/S.mean()).round(3).T.to_string())
R = {}
for k in S:
    prof = S[k].groupby(dw).transform('mean'); R[k] = S[k]/prof
R = pd.DataFrame(R)
print("sd residuo diario vs Poisson:"); print(pd.DataFrame({'sd_res': R.std(), 'poisson': 1/np.sqrt(S.mean()), 'p1': R.quantile(0.01), 'p99': R.quantile(0.99)}).round(4).to_string())
print("correlación de residuos diarios entre tablas:"); print(R.corr().round(3).to_string())
for lag in [1, -1, 7]:
    print("lag", lag, "corr(tx_t, cc_t+lag)=", round(R.tx.corr(R.cc.shift(-lag)), 3), " corr(tx, de)=", round(R.tx.corr(R.de.shift(-lag)), 3))
# horas
for t, e in [('tx', "hour(ts)"), ('cc', "hour(ts)"), ('de', "hour(ts)"), ('cs', "hour(ts)"), ('cp', "hour(ts)")]:
    h = con.execute(f"SELECT {e} h, count(*) n FROM {t} GROUP BY 1 ORDER BY 1").fetchdf()
    r = h.n/h.n.mean(); print(t, "hora ts: min", round(r.min(), 3), "max", round(r.max(), 3), "argmax", int(h.h[r.idxmax()]), "argmin", int(h.h[r.idxmin()]))
print(con.execute("SELECT min(ts), max(ts) FROM de").fetchdf(), con.execute("SELECT min(ts), max(ts) FROM cs").fetchdf())
