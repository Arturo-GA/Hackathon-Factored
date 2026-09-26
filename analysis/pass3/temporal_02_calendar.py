"""H2-H5: efectos de calendario en volumen de tx usando fecha local = process_date.
Día de semana, día del mes (quincena 1/15, fin de mes), mes, año/tendencia; por país, tipo, canal, estado."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

d = con.execute("""SELECT process_date d, country, ttype, channel, status, count(*) n, sum(amount_usd) s_usd, count(amount_usd) n_usd
  FROM tx GROUP BY ALL""").fetchdf()
d['d'] = pd.to_datetime(d['d'])
print("filas agregadas", len(d))
days = pd.DataFrame({'d': pd.date_range('2023-06-17', '2026-06-17')})
days['dow'] = days.d.dt.dayofweek; days['dom'] = days.d.dt.day; days['month'] = days.d.dt.month
days['eom'] = (days.d + pd.Timedelta(days=1)).dt.day == 1

tot = d.groupby('d').n.sum().reindex(days.d, fill_value=0).reset_index(); tot.columns = ['d', 'n']
tot = tot.merge(days, on='d')
print("días", len(tot), "media diaria", tot.n.mean().round(1), "sd", tot.n.std().round(1), "CV", (tot.n.std()/tot.n.mean()).round(4),
      "Poisson sd esperado", np.sqrt(tot.n.mean()).round(1))
print("min/max diario", tot.n.min(), tot.n.max())
print("por dow (0=lun):", (tot.groupby('dow').n.mean()/tot.n.mean()).round(4).to_dict())
r = tot.groupby('dom').n.mean()/tot.n.mean(); print("por dom rango", r.min().round(4), r.max().round(4)); print(r.round(3).to_dict())
print("fin de mes vs resto:", (tot[tot.eom].n.mean()/tot[~tot.eom].n.mean()).round(4))
print("por mes:", (tot.groupby('month').n.mean()/tot.n.mean()).round(4).to_dict())
tot['ym'] = tot.d.dt.to_period('M')
m = tot.groupby('ym').n.mean(); print("media diaria por mes calendario (primeros/últimos):"); print(m.head(4).round(0).to_dict(), m.tail(4).round(0).to_dict())
print("año:", tot.groupby(tot.d.dt.year).n.mean().round(1).to_dict())
# tendencia lineal
x = (tot.d - tot.d.min()).dt.days.values; b = np.polyfit(x, tot.n.values, 1); print("pendiente tx/día por día", b[0].round(4), "=> cambio en 3 años %", (b[0]*1096/b[1]*100).round(2))

def dim_profile(dim):
    g = d.groupby(['d', dim]).n.sum().unstack(fill_value=0).reindex(days.d, fill_value=0)
    g = g.join(days.set_index('d'))
    out = {}
    for c in [c for c in g.columns if c not in ('dow', 'dom', 'month', 'eom')]:
        mu = g[c].mean()
        dw = g.groupby('dow')[c].mean()/mu; dm = g.groupby('dom')[c].mean()/mu; mo = g.groupby('month')[c].mean()/mu
        yr = g.groupby(g.index.year)[c].mean()/mu
        out[c] = dict(n=int(g[c].sum()), dow_min=dw.min(), dow_max=dw.max(), dom_min=dm.min(), dom_max=dm.max(),
                      d1=dm[1], d15=dm[15], d30=dm.get(30), mo_min=mo.min(), mo_max=mo.max(), y2023=yr.get(2023), y2026=yr.get(2026))
    print(f"--- perfil por {dim} (razones vs media de esa serie)"); print(pd.DataFrame(out).T.round(3).to_string())
for dim in ['country', 'ttype', 'channel', 'status']:
    dim_profile(dim)
