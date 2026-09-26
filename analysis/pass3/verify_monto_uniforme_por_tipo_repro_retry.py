# Verificacion independiente (reintento) de "monto_uniforme_por_tipo" - parte 1: limites, forma de la distribucion, digitos
import duckdb, numpy as np, pandas as pd
from scipy import stats
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
q = lambda s: con.execute(s).df()

LO = {'Purchase': 5, 'Withdrawal': 20, 'Payment': 50, 'Adjustment': 10, 'Deposit': 50, 'Transfer': 100}
HI = {'Purchase': 500, 'Withdrawal': 500, 'Payment': 2000, 'Adjustment': 1000, 'Deposit': 5000, 'Transfer': 10000}
K = "(case currency when 'ARS' then 350.0 when 'COP' then 4000.0 when 'USD' then 1.0 end)"
LOs = "(case ttype " + " ".join(f"when '{t}' then {v}" for t, v in LO.items()) + " end)"
HIs = "(case ttype " + " ".join(f"when '{t}' then {v}" for t, v in HI.items()) + " end)"
con.execute(f"""create temp view v as select ttype, currency, channel, amount, amount/{K} a, {LOs} lo, {HIs} hi,
  (amount/{K} - {LOs})/({HIs}-{LOs}) u from tx""")

print("== 1) Limites por ttype x moneda (a = amount/K; K: ARS 350, COP 4000, USD 1)")
b = q("""select ttype, currency, count(*) n, min(a) min_a, max(a) max_a,
  sum((a >= lo - 1e-9 and a <= hi + 1e-9)::int) n_in, min(lo) lo, min(hi) hi,
  sum((amount is null)::int) n_null, sum((amount<=0)::int) n_nonpos
  from v group by all order by 1,2""")
b['gap_lo'] = b.min_a - b.lo; b['gap_hi'] = b.hi - b.max_a; b['gap_esperado'] = (b.hi - b.lo) / (b.n + 1)
print(b.to_string(index=False))
print("TOTAL filas:", b.n.sum(), " dentro de limites:", b.n_in.sum(), " fuera:", b.n.sum() - b.n_in.sum())
# que tan cerca queda cada limite en unidades del gap esperado
print("max gap_lo/gap_esperado=%.2f  max gap_hi/gap_esperado=%.2f" % ((b.gap_lo / b.gap_esperado).max(), (b.gap_hi / b.gap_esperado).max()))
# con otros K alternativos: cuantas filas saldrian de rango si se usa la tasa fx real (sanity: ARS se devaluo)
print(q("select dst, min(rate) mn, max(rate) mx, avg(rate) av from fx where src='USD' and dst in ('ARS','COP','MXN') group by all order by 1").to_string(index=False))

print("\n== 2) Chi2 por celda (20 y 100 bins) sobre TODAS las filas; media y varianza de u (esperado 0.5 y 1/12=0.08333)")
rows = []
for nb in (20, 100):
    h = q(f"select ttype, currency, least(floor(u*{nb}),{nb-1})::int b, count(*) n from v group by all")
    for (t, c), g in h.groupby(['ttype', 'currency']):
        cnt = np.zeros(nb); cnt[g.b.values] = g.n.values
        chi = stats.chisquare(cnt)
        rows.append(dict(ttype=t, cur=c, bins=nb, n=int(cnt.sum()), chi2=round(chi.statistic, 1), p=chi.pvalue,
                         maxdev=np.max(np.abs(cnt / cnt.mean() - 1)), maxdev_z=np.max(np.abs(cnt - cnt.mean()) / np.sqrt(cnt.mean()))))
r = pd.DataFrame(rows)
print(r[r.bins == 20].to_string(index=False, float_format=lambda x: '%.4g' % x))
print("20 bins: min p=%.3g  max maxdev=%.3f | 100 bins: min p=%.3g  max maxdev=%.3f" % (
    r[r.bins == 20].p.min(), r[r.bins == 20].maxdev.max(), r[r.bins == 100].p.min(), r[r.bins == 100].maxdev.max()))
# prueba conjunta: suma de chi2 sobre las 18 celdas (20 bins)
s = r[r.bins == 20]; print("chi2 conjunto 20 bins: %.1f con %d gl, p=%.3g" % (s.chi2.sum(), 19 * len(s), stats.chi2.sf(s.chi2.sum(), 19 * len(s))))
s = r[r.bins == 100]; print("chi2 conjunto 100 bins: %.1f con %d gl, p=%.3g" % (s.chi2.sum(), 99 * len(s), stats.chi2.sf(s.chi2.sum(), 99 * len(s))))
m = q("select ttype, currency, count(*) n, avg(u) mean_u, var_samp(u) var_u, skewness(u) skew, kurtosis(u) kurt_exc from v group by all order by 1,2")
m['z_mean'] = (m.mean_u - 0.5) / np.sqrt(1 / 12 / m.n)
print(m.to_string(index=False, float_format=lambda x: '%.5f' % x))
print("(uniforme: skew 0, kurtosis exceso -1.2)")

print("\n== 3) KS sobre TODAS las filas con histograma de 10,000 bins (error de D <= ~2e-4): uniforme vs log-uniforme")
NB = 10000
h = q(f"select ttype, currency, least(floor(u*{NB}),{NB-1})::int b, count(*) n from v group by all")
ks_rows = []
for key, g in list(h.groupby('ttype')) + list(h.groupby(['ttype', 'currency'])):
    t = key if isinstance(key, str) else key[0]
    cnt = np.bincount(g.b.values, weights=g.n.values, minlength=NB)
    n = cnt.sum(); ecdf = np.cumsum(cnt) / n
    edges_u = np.arange(1, NB + 1) / NB
    D_u = np.max(np.abs(ecdf - edges_u))
    a_edges = LO[t] + edges_u * (HI[t] - LO[t])
    F_log = np.log(a_edges / LO[t]) / np.log(HI[t] / LO[t])
    D_log = np.max(np.abs(ecdf - F_log))
    ks_rows.append(dict(celda=key if isinstance(key, str) else f"{key[0]}-{key[1]}", n=int(n), D_unif=D_u,
                        p_unif=stats.kstwobign.sf(D_u * np.sqrt(n)), D_logunif=D_log))
ks = pd.DataFrame(ks_rows)
print(ks.to_string(index=False, float_format=lambda x: '%.4g' % x))
print("D_unif max=%.4f ; D_logunif rango por ttype = %.3f-%.3f" % (ks.D_unif.max(), ks[~ks.celda.str.contains('-')].D_logunif.min(), ks[~ks.celda.str.contains('-')].D_logunif.max()))

print("\n== 4) Decimales / enteros / centavos")
print(q(f"""select currency, count(*) n,
  avg((abs(amount*100 - round(amount*100)) < 1e-6)::int) en_grilla_2dec,
  avg((amount = floor(amount))::int) entero,
  avg((abs(a*100 - round(a*100)) < 1e-6)::int) a_usd_en_grilla_2dec
  from v group by 1 order by 1""").to_string(index=False))
c = q("select currency, (round(amount*100)::bigint % 100)::int cents, count(*) n from v group by all")
for cur, g in c.groupby('currency'):
    cnt = np.bincount(g.cents.values, weights=g.n.values, minlength=100)
    chi = stats.chisquare(cnt)
    print(f"centavos {cur}: chi2={chi.statistic:.1f} (99 gl) p={chi.pvalue:.3g}  share .00={cnt[0]/cnt.sum():.4f}  maxdev={np.max(np.abs(cnt/cnt.mean()-1)):.3f}")
print(q("""select ttype, channel, currency, count(*) n, avg((amount <> floor(amount))::int) con_centavos
  from v where ttype='Withdrawal' group by all order by 1,2,3""").to_string(index=False))

print("\n== 5) Primer digito (USD) vs Benford vs prediccion teorica de la mezcla de uniformes")
fd = q("select ttype, cast(substr(cast(cast(floor(amount) as bigint) as varchar),1,1) as int) d, count(*) n from tx where currency='USD' group by all")
obs = fd.groupby('d').n.sum(); obs = obs / obs.sum()
mix = fd.groupby('ttype').n.sum(); mix = mix / mix.sum()
def p_digit(lo, hi, d):
    tot = 0.0
    for k in range(0, 6):
        a0, a1 = d * 10 ** k, (d + 1) * 10 ** k
        tot += max(0.0, min(a1, hi) - max(a0, lo))
    return tot / (hi - lo)
theo = pd.Series({d: sum(mix[t] * p_digit(LO[t], HI[t], d) for t in mix.index) for d in range(1, 10)})
benf = pd.Series({d: np.log10(1 + 1 / d) for d in range(1, 10)})
print(pd.DataFrame({'observado': obs.round(4), 'teorico_mezcla_uniformes': theo.round(4), 'benford': benf.round(4)}).T.to_string())
