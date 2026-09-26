# Verificacion independiente del hallazgo fx_ruido_iid (tabla fx = ruido iid alrededor de tasas fijas)
import duckdb, numpy as np, pandas as pd
from scipy import stats

con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)

fx = con.execute("select * from fx").df()          # 13k filas: cabe en memoria
fx['date'] = pd.to_datetime(fx['date'])
fx['pair'] = fx.src + '>' + fx.dst
print('== 0. Estructura')
print('filas', len(fx), '| fechas', fx.date.nunique(), fx.date.min().date(), '->', fx.date.max().date())
cal = pd.date_range(fx.date.min(), fx.date.max(), freq='D')
print('dias calendario', len(cal), '| fechas faltantes', len(set(cal) - set(fx.date)),
      '| % fechas fin de semana', round((pd.Series(fx.date.unique()).dt.dayofweek >= 5).mean() * 100, 1))
print('pares', fx.pair.nunique(), '| filas por par min/max', fx.groupby('pair').size().min(), fx.groupby('pair').size().max(),
      '| duplicados (date,src,dst)', fx.duplicated(['date', 'src', 'dst']).sum(), '| nulos', int(fx.isna().sum().sum()))

# ---- 1. Centro fijo y ruido relativo u = rate/centro - 1
C = {'USD': 1.0, 'MXN': 17.0, 'ARS': 350.0, 'COP': 4000.0}
fx['center'] = fx.dst.map(C) / fx.src.map(C)
fx['u'] = fx.rate / fx.center - 1
fx['y'] = fx.date.dt.year


def ndec(x):
    for k in range(0, 12):
        if np.all(np.abs(x - np.round(x, k)) < 1e-9 * np.maximum(1, np.abs(x))):
            return k
    return 99


def ljung_box(x, h=20):
    x = x - x.mean(); n = len(x); d = (x * x).sum()
    rho = np.array([(x[k:] * x[:-k]).sum() / d for k in range(1, h + 1)])
    Q = n * (n + 2) * np.sum(rho ** 2 / (n - np.arange(1, h + 1)))
    return Q, stats.chi2.sf(Q, h), rho


print('\n== 1. Por par: niveles, ruido relativo u, tendencia, autocorrelacion')
rows = []
for p, s in fx.sort_values('date').groupby('pair'):
    r = s.rate.values; u = s.u.values; t = (s.date - s.date.min()).dt.days.values
    lr = stats.linregress(t, u)
    Q, pq, rho = ljung_box(u, 20)
    ym = s.groupby('y').rate.mean()
    rows.append(dict(pair=p, center=round(s.center.iloc[0], 6), mn=r.min(), med=np.median(r), mx=r.max(),
                     u_min=u.min() * 100, u_max=u.max() * 100, u_sd=u.std() * 100, exkurt=stats.kurtosis(u),
                     ymean_min_pct=(ym.min() / s.center.iloc[0] - 1) * 100, ymean_max_pct=(ym.max() / s.center.iloc[0] - 1) * 100,
                     trend_tot_pct=lr.slope * t.max() * 100, trend_R2=lr.rvalue ** 2, ac1=rho[0], ac7=rho[6],
                     LB20_p=pq, sd_chg1=np.std(r[1:] / r[:-1] - 1) * 100, sd_chg30=np.std(r[30:] / r[:-30] - 1) * 100,
                     sd_chg365=np.std(r[365:] / r[:-365] - 1) * 100, ndec=ndec(r), ndistinct=len(np.unique(r))))
T = pd.DataFrame(rows).set_index('pair')
print(T.round(4).to_string())
print('u global: min %.3f%%  max %.3f%%  sd %.3f%% (uniforme +-2%% => sd %.3f%%)  exkurt %.2f (uniforme -1.2, normal 0)'
      % (fx.u.min() * 100, fx.u.max() * 100, fx.u.std() * 100, 4 / np.sqrt(12), stats.kurtosis(fx.u)))
big = fx[fx.rate > 5]                      # pares donde el redondeo a 6 decimales no distorsiona u
print('KS u ~ U(-2%%,2%%) en pares con rate>5 (n=%d): D=%.4f p=%.3g' % (len(big), *stats.kstest(big.u, 'uniform', args=(-0.02, 0.04))))
print('KS u ~ Normal(0, sd) mismos pares: D=%.4f p=%.3g' % stats.kstest(big.u / big.u.std(), 'norm'))
print('abs(u) mediana %.3f%%, p95 %.3f%%' % (fx.u.abs().median() * 100, fx.u.abs().quantile(.95) * 100))

print('\n== 1b. USD->* medias anuales (tasas)')
print(fx[fx.src == 'USD'].pivot_table(index='y', columns='dst', values='rate', aggfunc='mean').round(3).to_string())
ua = fx[fx.pair == 'USD>ARS'].sort_values('date')
print('USD>ARS: min %.3f med %.3f max %.3f | primer mes %.2f ultimo mes %.2f' % (
    ua.rate.min(), ua.rate.median(), ua.rate.max(), ua.rate.head(30).mean(), ua.rate.tail(30).mean()))

# ---- 2. Independencia entre pares el mismo dia (factor comun?)
P = fx.pivot_table(index='date', columns='pair', values='rate')
U = fx.pivot_table(index='date', columns='pair', values='u')
cm = U.corr().values; iu = np.triu_indices_from(cm, 1)
ev = np.linalg.eigvalsh(np.corrcoef(U.values.T))
print('\n== 2. Correlacion de u entre los 12 pares (mismo dia): media %.4f, max|r| %.4f; 1er componente principal explica %.1f%% (iid => ~8.3%% + ruido)'
      % (cm[iu].mean(), np.abs(cm[iu]).max(), ev.max() / ev.sum() * 100))

# ---- 3. Consistencia de inversas
print('\n== 3. Inversas: rate(A>B)*rate(B>A)')
for a, b in [('USD', 'MXN'), ('USD', 'COP'), ('USD', 'ARS'), ('MXN', 'COP'), ('MXN', 'ARS'), ('COP', 'ARS')]:
    prod = P[f'{a}>{b}'] * P[f'{b}>{a}']
    c = np.corrcoef(U[f'{a}>{b}'], U[f'{b}>{a}'])[0, 1]
    print(f'  {a}<->{b}: media {prod.mean():.4f} sd {prod.std() * 100:.2f}% min {prod.min():.4f} max {prod.max():.4f} '
          f'| |prod-1|<0.1%: {(abs(prod - 1) < 0.001).mean() * 100:.1f}% | corr(u_AB,u_BA)={c:+.3f} (inversa exacta => -1)')

# ---- 4. Triangulacion: todas las rutas A>C vs A>B * B>C
print('\n== 4. Triangulacion')
cur = ['USD', 'MXN', 'COP', 'ARS']; tri = []
for a in cur:
    for c in cur:
        for b in cur:
            if len({a, b, c}) == 3:
                x = P[f'{a}>{c}'] / (P[f'{a}>{b}'] * P[f'{b}>{c}'])
                tri.append(dict(route=f'{a}>{c} vs {a}>{b}>{c}', mean=x.mean(), sd=x.std() * 100, mn=x.min(), mx=x.max(),
                                within01=(abs(x - 1) < 0.001).mean() * 100))
TR = pd.DataFrame(tri)
print(TR[TR.route == 'USD>ARS vs USD>MXN>ARS'].round(4).to_string(index=False))
print('  24 rutas: sd%% min %.2f max %.2f media %.2f (iid U+-2%% => sqrt(3)*1.155 = %.2f) | media ratio %.4f..%.4f | %% dias dentro de 0.1%%: %.1f'
      % (TR.sd.min(), TR.sd.max(), TR.sd.mean(), np.sqrt(3) * 4 / np.sqrt(12), TR['mean'].min(), TR['mean'].max(), TR.within01.mean()))

# ---- 5. Efectos calendario (dia de semana / mes) sobre u
print('\n== 5. Efectos calendario sobre u (eta^2)')
fx['dow'] = fx.date.dt.dayofweek; fx['mon'] = fx.date.dt.month
for col in ['dow', 'mon']:
    e = []
    for p, s in fx.groupby('pair'):
        g = [grp.u.values for _, grp in s.groupby(col)]
        f, pv = stats.f_oneway(*g)
        ss_b = sum(len(x) * (x.mean() - s.u.mean()) ** 2 for x in g); ss_t = ((s.u - s.u.mean()) ** 2).sum()
        e.append((ss_b / ss_t, pv))
    e = np.array(e)
    print(f'  {col}: eta2 max {e[:, 0].max():.4f} media {e[:, 0].mean():.4f}; p<0.05 en {(e[:, 1] < 0.05).sum()}/12 pares')

# ---- 6. buy / sell
fx['bside'] = (fx.rate - fx.buy) / fx.rate; fx['sside'] = (fx.sell - fx.rate) / fx.rate; fx['spread'] = (fx.sell - fx.buy) / fx.rate
print('\n== 6. buy/sell')
print('  buy<rate<sell: %.4f%% | spread (sell-buy)/rate: min %.3f%% media %.3f%% max %.3f%%'
      % (((fx.buy < fx.rate) & (fx.rate < fx.sell)).mean() * 100, fx.spread.min() * 100, fx.spread.mean() * 100, fx.spread.max() * 100))
bb = fx[fx.rate > 5]
print('  (pares rate>5) lado compra min %.3f%% max %.3f%% | lado venta min %.3f%% max %.3f%% | corr lados %.4f | |lado_c - lado_v| mediana %.5f%%'
      % (bb.bside.min() * 100, bb.bside.max() * 100, bb.sside.min() * 100, bb.sside.max() * 100,
         np.corrcoef(bb.bside, bb.sside)[0, 1], (bb.bside - bb.sside).abs().median() * 100))
print('  KS medio-spread h ~ U(0.5%%,1.5%%) (pares rate>5, n=%d): D=%.4f p=%.3g' % (len(bb), *stats.kstest(bb.bside, 'uniform', args=(0.005, 0.01))))
print('  (pares rate>5) spread min %.3f%% media %.3f%% max %.3f%% | (pares rate<1) spread min %.3f%% max %.3f%%'
      % (bb.spread.min() * 100, bb.spread.mean() * 100, bb.spread.max() * 100,
         fx[fx.rate < 1].spread.min() * 100, fx[fx.rate < 1].spread.max() * 100))
print('  corr(spread, |u|) = %.4f ; corr(spread,u) = %.4f' % (np.corrcoef(fx.spread, fx.u.abs())[0, 1], np.corrcoef(fx.spread, fx.u)[0, 1]))
H = bb.pivot_table(index='date', columns='pair', values='bside'); hc = H.corr().values; ih = np.triu_indices_from(hc, 1)
print('  corr de h entre pares (rate>5) mismo dia: media %.4f max|r| %.4f | ac1 h USD>ARS %.4f'
      % (hc[ih].mean(), np.abs(hc[ih]).max(), H['USD>ARS'].autocorr(1)))

# ---- 7. source
print('\n== 7. source')
print(fx.source.value_counts().to_string())


def cramer(a, b):
    ct = pd.crosstab(a, b); chi, pv, _, _ = stats.chi2_contingency(ct)
    return np.sqrt(chi / (ct.values.sum() * (min(ct.shape) - 1))), pv


for nm, col in [('par', fx.pair), ('anio', fx.y), ('dia semana', fx.dow)]:
    V, pv = cramer(fx.source, col); print(f'  source x {nm}: V={V:.4f} p={pv:.3g}')
e = fx.groupby('source').u.agg(['mean', 'std', 'count']); print((e.assign(mean=e['mean'] * 100, std=e['std'] * 100)).round(4).to_string())
f, pv = stats.f_oneway(*[g.u.values for _, g in fx.groupby('source')]); print(f'  ANOVA u ~ source: p={pv:.3g}')
f, pv = stats.f_oneway(*[g.spread.values for _, g in fx.groupby('source')]); print(f'  ANOVA spread ~ source: p={pv:.3g}')
nd = fx.groupby('date').source.nunique()
print('  fuentes distintas por fecha: media %.3f (asignacion iid uniforme => %.3f)' % (nd.mean(), 4 * (1 - 0.75 ** 12)))

# ---- 8. Precision de pares pequenos
print('\n== 8. Precision (6 decimales)')
for p in ['COP>USD', 'ARS>USD', 'COP>MXN', 'MXN>USD', 'ARS>MXN', 'COP>ARS']:
    s = fx[fx.pair == p].rate
    print(f'  {p}: min {s.min():.6f} max {s.max():.6f} distintos {s.nunique()} | error max redondeo relativo {0.5e-6 / s.min() * 100:.3f}%')

# ---- 9. amount_usd vs fx del dia (implicacion 'puede diferir ~1%')
print('\n== 9. tx: amount/amount_usd vs tasa fija y vs fx del dia (amount_usd>=10)')
print(con.execute("""
 with t as (select currency, ts::date d, amount, amount_usd from tx where amount_usd >= 10 and currency in ('ARS','COP'))
 select t.currency, count(*) n,
   median(abs(t.amount/t.amount_usd/(case t.currency when 'ARS' then 350 else 4000 end)-1))*100 med_err_fija_pct,
   median(abs(t.amount/t.amount_usd/f.rate-1))*100 med_err_fx_pct,
   quantile_cont(abs(t.amount/t.amount_usd/f.rate-1),0.95)*100 p95_err_fx_pct,
   avg((abs(t.amount/t.amount_usd/f.rate-1)<0.001)::int)*100 pct_match_fx_01
 from t join fx f on f.date=t.d and f.src='USD' and f.dst=t.currency group by all order by 1""").df().round(4).to_string())
