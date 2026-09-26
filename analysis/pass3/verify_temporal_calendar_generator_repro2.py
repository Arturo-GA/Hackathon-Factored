"""Verificación independiente (intento 2) del hallazgo temporal_calendar_generator.
Afirmación: n_dia = base x (1 lun-vie | 0,60 finde en tx; 0,50 en cc/cp/sv) x U(0,8;1,2) i.i.d., compartido dentro de tx,
independiente entre tablas; la caída del lunes es artefacto de ts::DATE; dos medias alcanzan el piso de MAPE (~10%).

Secciones (todo agregado en SQL; pandas solo con series diarias de <=1100 filas):
 A. Perfil semanal por process_date y por ts::DATE (razón finde/semana con bootstrap POR SEMANAS, igualdad lun-vie).
 B. Mecanismo del artefacto: perfil ts::DATE predicho = mezcla del perfil process_date con la distribución de desfase (días).
 C. Forma del residuo: ¿acotado en [0,8;1,2]? max/min por clase vs simulación pura U vs U x Poisson (clave: cp ~60/día).
 D. Estructura temporal del residuo: autocorrelación, Ljung-Box, año, mes, día del mes, feriados, tendencia.
 E. Multiplicador compartido dentro de tx (y cc): dispersión multinomial de la composición diaria y correlaciones vs simulación H0.
 F. Independencia entre tablas (tx, cc, cp, sv, de) + rezagos (tx / rechazos / fraude -> cc, cc Transaccional, cp).
 G. sv vs cc: ¿sv diario = round(0,31 x cc diario)? y enlace por interaction_id.
 H. Pronóstico: dos medias, 7 medias, naive t-7, constante óptima, piso teórico, y modelos con rezagos (Ridge/GBM).
"""
import duckdb, pandas as pd, numpy as np
from scipy import stats
from sklearn.linear_model import Ridge
from sklearn.ensemble import GradientBoostingRegressor

pd.set_option('display.width', 250)
rng = np.random.default_rng(20260926)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")

P0, P1 = pd.Timestamp('2023-06-17'), pd.Timestamp('2026-06-17')
IDX = pd.date_range(P0, P1)
DOW = ['lun', 'mar', 'mie', 'jue', 'vie', 'sab', 'dom']


def daily(table, dexpr='process_date', where='TRUE'):
    d = con.execute(f"SELECT {dexpr} AS d, count(*) AS n FROM {table} WHERE {where} GROUP BY 1").fetchdf()
    d['d'] = pd.to_datetime(d['d'])
    return d.set_index('d')['n'].sort_index().astype(float)


def two_mean_resid(s):
    we = s.index.dayofweek >= 5
    r = s.copy()
    r[we] = s[we] / s[we].mean(); r[~we] = s[~we] / s[~we].mean()
    return r


def dow_resid(s):
    return s / s.groupby(s.index.dayofweek).transform('mean')


def week_block_ci(s, B=3000):
    """IC95 de la razón media finde / media lun-vie remuestreando semanas completas (lun-dom)."""
    wk = (s.index - pd.Timestamp('2023-06-12')).days // 7  # 2023-06-12 es lunes
    df = pd.DataFrame({'n': s.values, 'wk': wk, 'we': s.index.dayofweek >= 5})
    g = df.groupby(['wk', 'we']).n.agg(['sum', 'count']).unstack(fill_value=0)
    swe, cwe, swd, cwd = g['sum'][True].values, g['count'][True].values, g['sum'][False].values, g['count'][False].values
    W = len(swe)
    ii = rng.integers(0, W, size=(B, W))
    rat = (swe[ii].sum(1) / cwe[ii].sum(1)) / (swd[ii].sum(1) / cwd[ii].sum(1))
    return np.percentile(rat, [2.5, 97.5])


def fisher_ci(r, n):
    z = np.arctanh(r); se = 1 / np.sqrt(n - 3)
    return np.tanh(z - 1.96 * se), np.tanh(z + 1.96 * se)


# ------------------------------------------------------------------ A + B
print("=" * 110); print("A. Perfil semanal por process_date y por ts::DATE (días extremos parciales de ts::DATE excluidos)")
S_pd = {}
for t in ['tx', 'cc', 'cp', 'sv']:
    kdist = con.execute(f"SELECT (CAST(ts AS DATE) - process_date) k, count(*) n FROM {t} GROUP BY 1 ORDER BY 1").fetchdf()
    f = (kdist.set_index('k').n / kdist.n.sum())
    kmax = int(kdist.k.max())
    prof = {}
    for lab, expr in [('process_date', 'process_date'), ('ts::DATE', 'CAST(ts AS DATE)')]:
        s = daily(t, expr)
        if lab == 'process_date':
            s = s.reindex(IDX, fill_value=0); S_pd[t] = s
        else:
            s = s[(s.index >= P0 + pd.Timedelta(days=kmax)) & (s.index <= P1)]
        dw = s.index.dayofweek; we = dw >= 5
        wdm = s[~we].mean()
        p = s.groupby(dw).mean() / wdm; prof[lab] = p
        ci = week_block_ci(s)
        an = stats.f_oneway(*[s[dw == k].values for k in range(5)]).pvalue
        kw = stats.kruskal(*[s[dw == k].values for k in range(5)]).pvalue
        ss = stats.ttest_ind(s[dw == 5].values, s[dw == 6].values).pvalue
        print(f"{t} {lab:12s} dias={len(s)} media lun-vie={wdm:8.1f} finde/semana={s[we].mean()/wdm:.4f} IC95(bloques semana)=[{ci[0]:.4f},{ci[1]:.4f}] "
              f"perfil {'/'.join(f'{x:.3f}' for x in p.values)}  ANOVA lun-vie p={an:.3g} KW p={kw:.3g} sab=dom p={ss:.3g}")
    # B: perfil ts::DATE predicho desde el perfil process_date y f_k
    pp = prof['process_date'].values
    pred = np.array([sum(f.get(k, 0) * pp[(d - k) % 7] for k in range(kmax + 1)) for d in range(7)])
    pred = pred / pred[:5].mean()
    obs = prof['ts::DATE'].values
    print(f"   B. desfase ts::DATE - process_date (días): {dict((int(k), round(v, 4)) for k, v in f.items())}")
    print(f"      perfil ts::DATE predicho {'/'.join(f'{x:.3f}' for x in pred)}  vs observado {'/'.join(f'{x:.3f}' for x in obs)}  max|dif|={np.abs(pred-obs).max():.4f}")

# uniformidad del desfase horario y si depende del día de semana (tx)
h = con.execute("""SELECT floor((epoch(ts) - epoch(process_date::TIMESTAMP))/3600)::INT hh, count(*) n FROM tx GROUP BY 1 ORDER BY 1""").fetchdf()
print(f"   tx desfase horario: bins {h.hh.min()}..{h.hh.max()} ({len(h)} bins), CV={h.n.std()/h.n.mean():.4f}")
fk = con.execute("""SELECT dayofweek(process_date) dw, avg((CAST(ts AS DATE) > process_date)::INT) f1 FROM tx GROUP BY 1 ORDER BY 1""").fetchdf()
print("   tx fracción con ts::DATE = process_date+1 por día de semana (0=dom):", fk.set_index('dw').f1.round(4).to_dict())

# ------------------------------------------------------------------ C
print("=" * 110); print("C. Forma del residuo diario (process_date): acotamiento y ruido Poisson adicional")
NS = 2000
for t in ['tx', 'cc', 'cp', 'sv']:
    s = S_pd[t]; we = s.index.dayofweek >= 5
    r = two_mean_resid(s)
    line = []
    for cls, m in [('lab', ~we), ('finde', we)]:
        x = s[m].values; base = x.mean(); nd = len(x)
        U = rng.uniform(0.8, 1.2, size=(NS, nd))
        pure = np.round(base * U); pois = rng.poisson(base * U)
        R_obs = x.max() / x.min()
        R_pure = pure.max(1) / pure.min(1); R_pois = pois.max(1) / np.maximum(pois.min(1), 1)
        sd_obs = (x / base).std(); sd_pure = (pure / pure.mean(1, keepdims=True)).std(1).mean()
        sd_pois = (pois / pois.mean(1, keepdims=True)).std(1).mean()
        out_obs = int(((x / base < 0.8) | (x / base > 1.2)).sum())
        out_pois = (((pois / base) < 0.8) | ((pois / base) > 1.2)).sum(1)
        line.append(f"  {cls}: base={base:.1f} n_dias={nd} max/min obs={R_obs:.4f} [puro U: {R_pure.mean():.4f} ({np.percentile(R_pure,2.5):.4f}-{np.percentile(R_pure,97.5):.4f}) | "
                    f"U x Poisson: {R_pois.mean():.4f} ({np.percentile(R_pois,2.5):.4f}-{np.percentile(R_pois,97.5):.4f})]; sd obs={sd_obs:.4f} puro={sd_pure:.4f} Poisson={sd_pois:.4f}; "
                    f"días fuera de [0,8;1,2] obs={out_obs} esperados con Poisson={out_pois.mean():.1f}")
    print(f"{t}: residuo min={r.min():.4f} max={r.max():.4f} sd={r.std():.4f} curtosis exceso={stats.kurtosis(r):.3f} (uniforme -1,2)")
    print("\n".join(line))
    if t == 'tx':
        base = np.where(we, s[we].mean(), s[~we].mean())
        hist, _ = np.histogram(r, bins=np.linspace(0.8, 1.2, 9))
        print("  histograma 8 bins en [0,8;1,2]:", hist.tolist(), "chi2 uniformidad p=%.3f" % stats.chisquare(hist).pvalue)
        print("  KS vs U(0,8;1,2) puro: p=%.3f" % stats.kstest(r.values, 'uniform', args=(0.8, 0.4)).pvalue)
        lam = rng.choice(base, 300000); sim = rng.poisson(lam * rng.uniform(0.8, 1.2, 300000)) / lam
        print("  KS vs U x Poisson (simulado): p=%.3f ; KS vs Normal(1, sd obs): p=%.2g" % (stats.ks_2samp(r.values, sim).pvalue,
              stats.ks_2samp(r.values, rng.normal(1, r.std(), 300000)).pvalue))
        print("  sd Poisson puro (1/sqrt(media))=%.4f ; sd teórica U(0,8;1,2)=%.4f" % (np.mean(1 / np.sqrt(base)), 0.4 / np.sqrt(12)))

# ------------------------------------------------------------------ D
print("=" * 110); print("D. Estructura temporal del residuo (dos medias, process_date)")
def ljungbox(x, H):
    x = np.asarray(x) - np.mean(x); n = len(x); den = np.sum(x * x)
    ac = np.array([np.sum(x[k:] * x[:-k]) / den for k in range(1, H + 1)])
    Q = n * (n + 2) * np.sum(ac ** 2 / (n - np.arange(1, H + 1)))
    return ac, Q, stats.chi2.sf(Q, H)
HOL = [(1, 1), (5, 1), (12, 25), (12, 24), (12, 31), (9, 16), (11, 2), (7, 20), (8, 7), (5, 25), (7, 9), (12, 8)]
for t in ['tx', 'cc', 'cp']:
    r = two_mean_resid(S_pd[t])
    ac, Q, p = ljungbox(r.values, 14)
    yrs = r.groupby(r.index.year).mean().round(4).to_dict()
    pm = stats.f_oneway(*[g.values for _, g in r.groupby(r.index.month)]).pvalue
    pdm = stats.f_oneway(*[g.values for _, g in r.groupby(r.index.day)]).pvalue
    tt = np.arange(len(r)) / 365.25
    sl = stats.linregress(tt, r.values)
    hol = r[[(d.month, d.day) in HOL for d in r.index]]
    th = stats.ttest_1samp(hol.values, 1.0)
    print(f"{t}: autocorr lag1..7={np.round(ac[:7],3).tolist()} (banda ±{1.96/np.sqrt(len(r)):.3f}); Ljung-Box Q(14)={Q:.1f} p={p:.3f}")
    print(f"    media por año={yrs}; ANOVA mes p={pm:.3f}; ANOVA día del mes p={pdm:.3f}; pendiente={sl.slope:+.4f}/año (p={sl.pvalue:.3f}); "
          f"feriados fijos n={len(hol)} media={hol.mean():.4f} (t p={th.pvalue:.3f})")

# ------------------------------------------------------------------ E
print("=" * 110); print("E. ¿Multiplicador compartido dentro de la tabla? dispersión multinomial de la composición diaria (H0 compartido => ~1)")
def pivot(table, col):
    d = con.execute(f"SELECT process_date d, {col} k, count(*) n FROM {table} GROUP BY ALL").fetchdf()
    d['d'] = pd.to_datetime(d['d'])
    P = d.pivot(index='d', columns='k', values='n').reindex(IDX).fillna(0)
    return P

def dispersion(P):
    X2 = 0.0; df = 0
    for cls in [False, True]:
        Q = P[(P.index.dayofweek >= 5) == cls].values
        E = Q.sum(1, keepdims=True) * (Q.sum(0) / Q.sum())[None, :]
        X2 += ((Q - E) ** 2 / E).sum(); df += (Q.shape[0] - 1) * (Q.shape[1] - 1)
    return X2 / df, stats.chi2.sf(X2, df)

def mean_corr(P):
    R = two_mean_resid_df(P); c = R.corr().values; iu = np.triu_indices_from(c, 1)
    return c[iu].mean(), c[iu].min()

def two_mean_resid_df(P):
    we = P.index.dayofweek >= 5; R = P.astype(float).copy()
    R[we] = P[we] / P[we].mean(); R[~we] = P[~we] / P[~we].mean(); return R

for table, col in [('tx', 'country'), ('tx', 'currency'), ('tx', 'ttype'), ('tx', 'channel'), ('tx', 'status'), ('cc', 'cat'), ('cc', 'channel')]:
    P = pivot(table, col)
    disp, pdisp = dispersion(P)
    mc_obs, mn_obs = mean_corr(P)
    # H0: total diario observado repartido multinomialmente con p fija por clase (lab/finde)
    sims_c, sims_d = [], []
    for _ in range(30):
        Z = np.zeros_like(P.values)
        for cls in [False, True]:
            m = (P.index.dayofweek >= 5) == cls
            Q = P.values[m]; p = Q.sum(0) / Q.sum()
            Z[m] = rng.multinomial(Q.sum(1).astype(np.int64), p)
        Zs = pd.DataFrame(Z, index=P.index, columns=P.columns)
        sims_c.append(mean_corr(Zs)[0])
    # contrafactual: multiplicador U independiente por categoría
    Zi = np.zeros_like(P.values)
    for cls in [False, True]:
        m = (P.index.dayofweek >= 5) == cls
        lam = P.values[m].mean(0)
        Zi[m] = np.round(lam[None, :] * rng.uniform(0.8, 1.2, size=(m.sum(), P.shape[1])))
    disp_ind, _ = dispersion(pd.DataFrame(Zi + 1e-9, index=P.index))
    we = P.index.dayofweek >= 5
    wr = (P[we].mean() / P[~we].mean()).round(3).to_dict()
    tot = P.values.sum()
    tab = np.vstack([P[~we].sum().values, P[we].sum().values])
    V = np.sqrt(stats.chi2_contingency(tab)[0] / tot)
    print(f"{table}.{col}: dispersión X2/gl={disp:.3f} (p={pdisp:.3f}) | si U independiente por categoría ~{disp_ind:.1f} | corr media residuos obs={mc_obs:.3f} "
          f"(min {mn_obs:.3f}) vs H0 compartido sim={np.mean(sims_c):.3f}±{np.std(sims_c):.3f} | finde/semana por cat={wr} | V(cat x finde)={V:.4f}")

# ------------------------------------------------------------------ F
print("=" * 110); print("F. Independencia entre tablas (residuo = n / media de su día de semana; de por (ts-6h)::DATE y por ts::DATE)")
ser = {k: S_pd[k] for k in ['tx', 'cc', 'cp', 'sv']}
ser['tx_decl'] = daily('tx', where="status='Declined'").reindex(IDX, fill_value=0)
ser['tx_fraud'] = daily('tx', where="fraud").reindex(IDX, fill_value=0)
ser['cc_trans'] = daily('cc', where="cat='Transaccional'").reindex(IDX, fill_value=0)
ser['cc_queja'] = daily('cc', where="cat='Queja'").reindex(IDX, fill_value=0)
de_loc = daily('de', "CAST(ts - INTERVAL 6 HOUR AS DATE)").reindex(IDX)
de_utc = daily('de', "CAST(ts AS DATE)").reindex(IDX)
ser['de_loc'] = de_loc; ser['de_utc'] = de_utc.iloc[1:]
ser['de_loc'] = ser['de_loc'].dropna(); ser['de_utc'] = ser['de_utc'].dropna()
for k in ['de_loc', 'de_utc']:
    s = ser[k]; p = s.groupby(s.index.dayofweek).mean(); p = p / p[:5].mean()
    print(f"  perfil {k}: {'/'.join(f'{x:.3f}' for x in p.values)}  sd residuo={dow_resid(s).std():.4f}  sd Poisson={1/np.sqrt(s.mean()):.4f}")
R = pd.DataFrame({k: dow_resid(v) for k, v in ser.items()})
cols = ['tx', 'cc', 'cp', 'sv', 'de_loc', 'de_utc', 'tx_decl', 'cc_trans']
print(R[cols].corr().round(3).to_string())
n = len(R.dropna())
for a, b in [('tx', 'cc'), ('tx', 'cp'), ('tx', 'sv'), ('cc', 'cp'), ('tx', 'de_loc'), ('cc', 'de_loc'), ('cp', 'de_loc'), ('cc', 'sv'), ('tx_decl', 'cc_trans')]:
    x = R[[a, b]].dropna(); c = x[a].corr(x[b]); lo, hi = fisher_ci(c, len(x))
    print(f"  corr({a},{b}) mismo día = {c:+.3f} IC95 [{lo:+.3f},{hi:+.3f}] n={len(x)}")
print("  rezagos k=1..7: corr(X_t, Y_t+k)")
for a, b in [('tx', 'cc'), ('tx_decl', 'cc'), ('tx_decl', 'cc_trans'), ('tx', 'cp'), ('tx_decl', 'cp'), ('tx_fraud', 'cp'), ('tx_fraud', 'cc_queja'), ('cc', 'cp')]:
    cs = [R[a].corr(R[b].shift(-k)) for k in range(1, 8)]
    j = int(np.argmax(np.abs(cs)))
    print(f"    {a:8s} -> {b:8s}: {np.round(cs,3).tolist()}  max|r|={abs(cs[j]):.3f} (k={j+1}); banda ±{1.96/np.sqrt(n):.3f}")
# regresión: ¿rezagos 0..7 de tx y rechazos explican el residuo de cc / cp? (R² ajustado)
for y in ['cc', 'cp', 'cc_trans']:
    X = pd.concat({f'{a}_l{k}': R[a].shift(k) for a in ['tx', 'tx_decl', 'tx_fraud'] for k in range(0, 8)}, axis=1)
    D = pd.concat([R[y], X], axis=1).dropna()
    Xm = np.column_stack([np.ones(len(D)), D.iloc[:, 1:].values]); yy = D.iloc[:, 0].values
    beta, *_ = np.linalg.lstsq(Xm, yy, rcond=None); res = yy - Xm @ beta
    r2 = 1 - res.var() / yy.var(); k = Xm.shape[1] - 1; r2a = 1 - (1 - r2) * (len(D) - 1) / (len(D) - k - 1)
    Fst = (r2 / k) / ((1 - r2) / (len(D) - k - 1)); pF = stats.f.sf(Fst, k, len(D) - k - 1)
    print(f"  OLS residuo {y} ~ tx, rechazos, fraude (rezagos 0..7, 24 vars): R²={r2:.4f} R²aj={r2a:+.4f} F p={pF:.3f}")

# ------------------------------------------------------------------ G
print("=" * 110); print("G. sv frente a cc")
m = pd.DataFrame({'cc': S_pd['cc'], 'sv': S_pd['sv']})
for lab, pred in [('round_half_up(0,31*cc)', np.floor(0.31 * m.cc + 0.5)), ('round_banker(0,31*cc)', np.round(0.31 * m.cc)),
                  ('floor(0,31*cc)', np.floor(0.31 * m.cc)), ('ceil(0,31*cc)', np.ceil(0.31 * m.cc))]:
    print(f"  sv == {lab}: {(pred == m.sv).sum()}/{len(m)} días; |dif| máx={np.abs(pred - m.sv).max():.0f}")
best = max(((fct, (np.floor(fct * m.cc + 0.5) == m.sv).mean()) for fct in np.round(np.arange(0.300, 0.3201, 0.0005), 4)), key=lambda z: z[1])
print(f"  mejor factor en rejilla 0,300-0,320: {best}")
j = con.execute("""SELECT count(*) n_sv, count(c.interaction_id) con_cc, avg((s.process_date = c.process_date)::INT) mismo_pd,
    count(DISTINCT s.interaction_id) int_distintas, avg((s.customer_id = c.customer_id)::INT) mismo_cliente,
    min(epoch(s.ts) - epoch(c.ts))/3600 dmin_h, max(epoch(s.ts) - epoch(c.ts))/3600 dmax_h
    FROM sv s LEFT JOIN cc c ON s.interaction_id = c.interaction_id""").fetchdf()
print(j.T.to_string())
print(f"  corr residuos sv-cc (dos medias) = {two_mean_resid(m.sv).corr(two_mean_resid(m.cc)):.4f}")

# ------------------------------------------------------------------ H
print("=" * 110); print("H. Pronóstico diario (train < 2025-06-17, test >= 2025-06-17)")
u = rng.uniform(0.8, 1.2, 2_000_000)
c_opt = np.sqrt(0.96)
print(f"  piso teórico MAPE: pred=media -> {np.mean(np.abs(u-1)/u)*100:.2f}% (analítico {2.5*np.log(1.25/1.2)*100:.2f}%); constante óptima c=sqrt(0,96)={c_opt:.4f} -> "
      f"{np.mean(np.abs(u-c_opt)/u)*100:.2f}% (analítico {2.5*(2-2*c_opt)*100:.2f}%)")
cut = pd.Timestamp('2025-06-17')
def mape(y, yh): return float(np.mean(np.abs(y - yh) / y) * 100)
Rtwo = pd.DataFrame({k: two_mean_resid(S_pd[k]) for k in ['tx', 'cc', 'cp', 'sv']})
Rtwo['tx_decl'] = two_mean_resid(ser['tx_decl'])
for t in ['tx', 'cc', 'cp', 'sv']:
    y = S_pd[t]; we = y.index.dayofweek >= 5; tr = y.index < cut; te = ~tr
    mwd, mwe = y[tr & ~we].mean(), y[tr & we].mean(); p2 = pd.Series(np.where(we, mwe, mwd), index=y.index)
    dm = y[tr].groupby(y.index[tr].dayofweek).mean(); p7 = pd.Series(dm.reindex(y.index.dayofweek).values, index=y.index)
    n7 = y.shift(7)
    # modelos con información disponible en t-1: rezagos 1..7 del residuo propio y de las otras tablas, calendario
    feats = {}
    for a in ['tx', 'cc', 'cp', 'tx_decl']:
        for k in range(1, 8):
            feats[f'{a}_l{k}'] = Rtwo[a].shift(k)
    F = pd.DataFrame(feats, index=y.index)
    F['dom'] = y.index.day; F['mes'] = y.index.month; F['dow'] = y.index.dayofweek
    target = y / p2 - 1
    ok = F.notna().all(1)
    trm, tem = tr & ok, te & ok
    rid = Ridge(alpha=10.0).fit(F[trm], target[trm]); ph_r = rid.predict(F[tem])
    gbm = GradientBoostingRegressor(n_estimators=200, max_depth=2, learning_rate=0.03, subsample=0.8, random_state=0).fit(F[trm], target[trm]); ph_g = gbm.predict(F[tem])
    r2r = 1 - np.mean((target[tem] - ph_r) ** 2) / np.mean((target[tem] - target[trm].mean()) ** 2)
    r2g = 1 - np.mean((target[tem] - ph_g) ** 2) / np.mean((target[tem] - target[trm].mean()) ** 2)
    yt = y[tem].values
    print(f"  {t}: n_test={te.sum()} | dos medias MAPE={mape(y[te].values, p2[te].values):.2f}% | x c_opt={mape(y[te].values, c_opt*p2[te].values):.2f}% | "
          f"7 medias={mape(y[te].values, p7[te].values):.2f}% | naive t-7={mape(y[te].values, n7[te].values):.2f}% | "
          f"Ridge rezagos: MAPE={mape(yt, p2[tem].values*(1+ph_r)):.2f}% R²res={r2r:+.3f} | GBM: MAPE={mape(yt, p2[tem].values*(1+ph_g)):.2f}% R²res={r2g:+.3f}")
print("fin")
