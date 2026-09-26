"""H11: ¿estado, código, fraude, fscore nulo varían con el tiempo (mes, dow, hora local, día del mes, año)?
Reporta rango de tasas y razón max/min con n."""
import duckdb, pandas as pd, numpy as np
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
dims = {
 'hour_local': "hour(ts - INTERVAL 6 HOUR)",
 'dow': "dayofweek(process_date)",
 'dom': "day(process_date)",
 'month': "month(process_date)",
 'quarter_idx': "strftime(date_trunc('quarter', process_date), '%Y-%m')",
 'weekend': "(dayofweek(process_date) IN (0,6))",
 'minute': "minute(ts)",
 'second': "second(ts)",
}
metrics = "count(*) n, avg((status='Declined')::INT) decl, avg((status='Pending')::INT) pend, avg((status='Reversed')::INT) rev, avg(fraud::INT) fraud, avg((fscore IS NULL)::INT) fs_null, avg(fscore) fs_mean, avg((code IS NULL)::INT) code_null"
rows = []
for k, e in dims.items():
    g = con.execute(f"SELECT {e} v, {metrics} FROM tx GROUP BY 1").fetchdf()
    for m in ['decl', 'pend', 'rev', 'fraud', 'fs_null', 'fs_mean', 'code_null']:
        rows.append((k, m, g.n.min(), g[m].min(), g[m].max(), g[m].max()/g[m].min(), np.average(g[m], weights=g.n)))
r = pd.DataFrame(rows, columns=['dim', 'metric', 'min_n', 'min', 'max', 'ratio', 'overall'])
print(r.round(5).to_string(index=False))
# chi2 aproximado para declinados vs hora local / mes
from scipy.stats import chi2_contingency
for k in ['hour_local', 'month', 'dow', 'dom']:
    g = con.execute(f"SELECT {dims[k]} v, status, count(*) n FROM tx GROUP BY ALL").fetchdf().pivot(index='v', columns='status', values='n').fillna(0)
    chi, p, dof, _ = chi2_contingency(g.values); V = np.sqrt(chi/(g.values.sum()*(min(g.shape)-1)))
    print(f"status x {k}: chi2={chi:.1f} dof={dof} p={p:.3g} V={V:.4f}")
# segundos: ¿redondeo? distribución de second==0
print(con.execute("SELECT avg((second(ts)=0)::INT) s0, avg((minute(ts)=0 AND second(ts)=0)::INT) m0s0 FROM tx").fetchdf())
