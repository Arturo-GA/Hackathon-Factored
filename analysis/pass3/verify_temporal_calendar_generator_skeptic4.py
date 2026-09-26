"""Verificador escéptico (reintento, parte 2): temporal_calendar_generator.
 H. ¿efectos de calendario escondidos en el residuo? mes, día del mes, quincena/fin de mes, año, feriados fijos MX/CO/AR.
 I. convergencia del nowcast intradía (6 h, 12 h, 18 h) en cc y tx, y base estable por año."""
import duckdb, pandas as pd, numpy as np
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
idx = pd.date_range('2023-06-18', '2026-06-16')
we = np.asarray(idx.dayofweek >= 5)
R = {}
for t in ['tx', 'cc', 'cp']:
    d = q(f"SELECT process_date d, count(*) n FROM {t} GROUP BY 1"); d['d'] = pd.to_datetime(d.d)
    s = d.set_index('d').n.reindex(idx).astype(float)
    R[t] = pd.Series(np.where(we, s / s[we].mean(), s / s[~we].mean()), index=idx)
R = pd.DataFrame(R)
hol = ['01-01', '05-01', '12-25', '12-24', '12-31', '09-16', '11-20', '02-05', '07-20', '08-07', '05-25', '07-09', '06-20', '12-08', '11-02']
md = np.asarray(idx.strftime('%m-%d')); ish = np.isin(md, hol)
print("== H. residuo vs calendario (process_date, sin extremos)")
for t in R:
    x = R[t]
    pm = stats.f_oneway(*[g.values for _, g in x.groupby(idx.month)]).pvalue
    pdm = stats.f_oneway(*[g.values for _, g in x.groupby(idx.day)]).pvalue
    eom = (idx + pd.Timedelta(days=1)).day == 1
    qn = np.isin(idx.day, [1, 2, 15, 16]) | eom
    yr = x.groupby(idx.year).mean().round(4).to_dict()
    print(f"{t}: ANOVA mes p={pm:.3f} | día del mes p={pdm:.3f} | quincena/fin de mes={x[qn].mean():.4f}±{1.96*x[qn].std()/np.sqrt(qn.sum()):.4f} (n={qn.sum()}) "
          f"| feriados fijos={x[ish].mean():.4f}±{1.96*x[ish].std()/np.sqrt(ish.sum()):.4f} (n={ish.sum()}) | media por año={yr}")
print("\n== I. nowcast intradía: MAPE en test (>=2025-06-17) según horas observadas de la ventana del process_date")
cut = pd.Timestamp('2025-06-17'); trm = np.asarray(idx < cut); tem = ~trm
off = {'tx': 6, 'cc': 8, 'cp': 8}
for t in ['tx', 'cc', 'cp']:
    cols = ", ".join(f"count(*) FILTER (WHERE (epoch(ts)-epoch(process_date::TIMESTAMP))/3600 < {off[t]}+{h}) n{h}" for h in [3, 6, 12, 18])
    g = q(f"SELECT process_date d, {cols}, count(*) n FROM {t} GROUP BY 1"); g['d'] = pd.to_datetime(g.d); g = g.set_index('d').reindex(idx)
    out = []
    for h in [3, 6, 12, 18]:
        k = g.n[trm].sum() / g[f'n{h}'][trm].sum()
        out.append(f"{h}h={np.mean(np.abs(g.n[tem] - k * g[f'n{h}'][tem]) / g.n[tem]) * 100:.2f}%")
    base = np.where(we, g.n[trm & we].mean(), g.n[trm & ~we].mean())
    print(f"  {t}: " + " | ".join(out) + f" | sin info del día (dos medias)={np.mean(np.abs(g.n[tem] - base[tem]) / g.n[tem]) * 100:.2f}%")
