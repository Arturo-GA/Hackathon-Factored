"""H8: sobredispersión diaria. ¿Hay un multiplicador por día común a países/tipos/canales? ¿autocorrelación?
Residuo = n_dia / media del mismo dow (global). Correlaciones entre series de residuos."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
idx = pd.date_range('2023-06-17', '2026-06-17')
def series(dim, where="TRUE"):
    d = con.execute(f"SELECT process_date d, {dim} k, count(*) n FROM tx WHERE {where} GROUP BY ALL").fetchdf()
    d['d'] = pd.to_datetime(d.d)
    p = d.pivot(index='d', columns='k', values='n').reindex(idx, fill_value=0).fillna(0)
    wd = p.index.dayofweek >= 5
    # residuo log vs media de su dow en ventana larga (dow global)
    ratio = p / p.groupby(wd).transform('mean')
    return p, ratio
for dim in ['country', 'ttype', 'channel', 'status', 'currency']:
    p, r = series(dim)
    c = np.log(r.clip(lower=1e-3)).corr()
    off = c.values[np.triu_indices_from(c, 1)]
    print(f"{dim}: corr media residuos log entre categorías={off.mean():.3f} (min {off.min():.3f}, max {off.max():.3f})")
p, r = series("'all'")
x = r['all']
print("sd residuo global", x.std().round(4), "Poisson esperado", (1/np.sqrt(p['all'].mean())).round(4))
for lag in [1, 2, 3, 7, 14, 30]:
    print("autocorr lag", lag, round(x.autocorr(lag), 3))
# rolling: ¿random walk suave?
print("sd de media móvil 7d del residuo", x.rolling(7).mean().std().round(4), " 30d", x.rolling(30).mean().std().round(4))
# ¿el multiplicador del día afecta monto medio o tasa de rechazo?
agg = con.execute("""SELECT process_date d, count(*) n, avg((status='Declined')::INT) decl, avg(fraud::INT) fr, median(amount_usd) med_usd,
   count(DISTINCT customer_id) ncust FROM tx GROUP BY 1""").fetchdf()
agg['d'] = pd.to_datetime(agg.d); agg = agg.set_index('d').reindex(idx)
agg['res'] = x
print(agg[["res","decl","fr","med_usd"]].corr().round(3))
agg['tx_per_cust'] = agg.n/agg.ncust
print("tx por cliente-día: media", agg.tx_per_cust.mean().round(4), "corr con residuo", agg[['res', 'tx_per_cust']].corr().iloc[0, 1].round(3))
# distribución del residuo (¿bimodal? ¿uniforme?)
print(np.percentile(x[p.index.dayofweek < 5], [1, 5, 25, 50, 75, 95, 99]).round(3))
print(np.percentile(x[p.index.dayofweek >= 5], [1, 5, 25, 50, 75, 95, 99]).round(3))
