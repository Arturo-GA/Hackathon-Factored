"""Verificador escéptico (reintento): temporal_calendar_generator.
Ataques nuevos:
 A. mecanismo del 'artefacto lunes': ¿se predice exactamente el perfil ts::DATE desde el perfil process_date + distribución del desfase?
 B. perfil semanal por process_date (tx, cc, cp, sv) con IC bootstrap, extremos recortados.
 C. ¿hay capa Poisson? cp (base ~71/día) es la prueba más potente: sd residuo 0.1155 (sin Poisson) vs ~0.166 (con Poisson).
 D. ¿multiplicador compartido dentro de tx? índice de dispersión de las participaciones diarias (=1 si reparto multinomial puro).
 E. ¿el multiplicador es por process_date? correlación entre tramos horarios dentro de la ventana vs a través del corte de día.
 F. independencia entre tablas (con rezagos) y regla sv = round(0.31*cc).
 G. pronóstico: dos medias vs piso; y nowcast intradía (primeras 6 h de la ventana) para probar 'ningún modelo puede superarlo'."""
import duckdb, pandas as pd, numpy as np
from scipy import stats
pd.set_option('display.width', 250)
rng = np.random.default_rng(123)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

print("== A0. rango de fechas y desfase ts - process_date (horas)")
OFF = {}
for t in ['tx', 'cc', 'cp', 'sv']:
    r = q(f"""SELECT min(process_date) pd0, max(process_date) pd1, min(ts) ts0, max(ts) ts1,
          min(epoch(ts)-epoch(process_date::TIMESTAMP))/3600 mn, max(epoch(ts)-epoch(process_date::TIMESTAMP))/3600 mx,
          avg((ts::DATE<>process_date)::INT) share_shift, count(*) n, count(process_date) n_pd FROM {t}""")
    print(t, r.to_dict('records')[0])
    OFF[t] = float(np.floor(r.mn[0]))
    h = q(f"""SELECT floor((epoch(ts)-epoch(process_date::TIMESTAMP))/3600)::INT hh, count(*) n FROM {t} GROUP BY 1 ORDER BY 1""")
    sh = h.n / h.n.sum()
    print(f"   desfase por hora: horas {h.hh.min()}..{h.hh.max()} n_bins={len(h)} share min={sh.min():.4f} max={sh.max():.4f} (uniforme=1/24={1/24:.4f})")
print("desfase por país en tx:")
print(q("""SELECT country, min(epoch(ts)-epoch(process_date::TIMESTAMP))/3600 mn, max(epoch(ts)-epoch(process_date::TIMESTAMP))/3600 mx, count(*) n
         FROM tx GROUP BY 1 ORDER BY 1""").round(2).to_string(index=False))

idx_all = pd.date_range('2023-06-17', '2026-06-17')
def daily(t, expr='process_date', where=''):
    d = q(f"SELECT {expr} AS d, count(*) AS n FROM {t} {where} GROUP BY 1"); d['d'] = pd.to_datetime(d.d)
    return d.set_index('d').n.reindex(idx_all).fillna(0).astype(float)

S = {t: daily(t) for t in ['tx', 'cc', 'cp', 'sv']}
T = {t: daily(t, 'CAST(ts AS DATE)') for t in ['tx', 'cc', 'cp']}
print("extremos process_date:", {t: (S[t].iloc[0], S[t].iloc[1], S[t].iloc[-2], S[t].iloc[-1]) for t in S})
D = pd.DataFrame(S).iloc[1:-1]            # recorta días posiblemente parciales
TD = pd.DataFrame(T).iloc[2:-2]
dow = D.index.dayofweek; we = np.asarray(dow >= 5)

print("\n== B. perfil semanal por process_date (relativo a media lun-vie), extremos recortados")
for t in D.columns:
    s = D[t]; prof = s.groupby(dow).mean() / s[~we].mean()
    bs = [rng.choice(s[we].values, we.sum()).mean() / rng.choice(s[~we].values, (~we).sum()).mean() for _ in range(2000)]
    kw = stats.kruskal(*[s[dow == k].values for k in range(5)]).pvalue
    ss = stats.mannwhitneyu(s[dow == 5], s[dow == 6]).pvalue
    print(f"{t}: lun..dom={prof.round(3).tolist()} finde/sem={s[we].mean()/s[~we].mean():.4f} IC95=[{np.percentile(bs,2.5):.4f},{np.percentile(bs,97.5):.4f}] KW lun-vie p={kw:.2f} sáb=dom p={ss:.2f}")

print("\n== A. ¿el perfil ts::DATE se predice mecánicamente? share(ts::DATE = pd) = s; perfil_ts(d) = s*P(d) + (1-s)*P(d-1)")
for t in ['tx', 'cc', 'cp']:
    s_same = 1 - q(f"SELECT avg((ts::DATE<>process_date)::INT) x FROM {t}").x[0]
    P = D[t].groupby(dow).mean(); P = P / P[:5].mean()
    pred = pd.Series([s_same * P[k] + (1 - s_same) * P[(k - 1) % 7] for k in range(7)])
    tdw = TD.index.dayofweek; obs = TD[t].groupby(tdw).mean(); obs = obs / D[t][~we].mean()
    print(f"{t}: s={s_same:.4f} predicho lun..dom={pred.round(3).tolist()}\n     observado ts::DATE     ={obs.round(3).tolist()}  max|dif|={np.abs(pred.values-obs.values).max():.4f}")

print("\n== C. residuo diario (process_date) y capa Poisson")
R = pd.DataFrame(index=D.index)
for t in D.columns:
    s = D[t]; bw, bf = s[~we].mean(), s[we].mean()
    R[t] = np.where(we, s / bf, s / bw)
    base = np.where(we, bf, bw)
    sd_pois = np.sqrt(np.mean(1 / base))
    # simulación con y sin Poisson para contar días fuera de [0.8,1.2]
    sim_np, sim_p = [], []
    for _ in range(200):
        u = rng.uniform(0.8, 1.2, len(base))
        sim_np.append(((np.round(base * u) / base < 0.8) | (np.round(base * u) / base > 1.2)).sum())
        y = rng.poisson(base * u) / base; sim_p.append(((y < 0.8) | (y > 1.2)).sum())
    out = ((R[t] < 0.8) | (R[t] > 1.2)).sum()
    print(f"{t}: base lun-vie={bw:.1f} finde={bf:.1f} | residuo min={R[t].min():.4f} max={R[t].max():.4f} sd={R[t].std():.4f} "
          f"(U sola {0.4/np.sqrt(12):.4f}; U+Poisson {np.sqrt(0.4**2/12 + sd_pois**2):.4f}) | días fuera [0.8,1.2]: obs={out} "
          f"sim_sin_Poisson={np.mean(sim_np):.1f} sim_con_Poisson={np.mean(sim_p):.1f} | curtosis={stats.kurtosis(R[t]):.3f}")
for t in D.columns:
    x = R[t]
    print(f"  {t}: autocorr lag1={x.autocorr(1):.3f} lag2={x.autocorr(2):.3f} lag7={x.autocorr(7):.3f}; corr con tiempo={np.corrcoef(np.arange(len(x)), x)[0,1]:.3f}")

print("\n== D. ¿multiplicador compartido dentro de tx? índice de dispersión de participaciones diarias (1 = multinomial puro)")
for col in ['country', 'ttype', 'channel', 'currency', 'status']:
    g = q(f"SELECT process_date d, {col} k, count(*) n FROM tx GROUP BY ALL"); g['d'] = pd.to_datetime(g.d)
    p = g.pivot(index='d', columns='k', values='n').reindex(D.index).fillna(0).astype(float)
    ntot = p.sum(axis=1)
    rows = []
    for c in p.columns:
        for wflag in [False, True]:
            m = we == wflag
            x = p[c][m]; n = ntot[m]; ph = x.sum() / n.sum()
            disp = (((x - n * ph) ** 2) / (n * ph * (1 - ph))).sum() / (m.sum() - 1)
            rows.append((c, wflag, ph, disp))
    rr = pd.DataFrame(rows, columns=['k', 'finde', 'share', 'disp'])
    # residuos por grupo: correlación
    res = p.copy()
    for c in p.columns:
        res.loc[we, c] = p.loc[we, c] / p.loc[we, c].mean(); res.loc[~we, c] = p.loc[~we, c] / p.loc[~we, c].mean()
    cm = res.corr().values; iu = np.triu_indices_from(cm, 1)
    fw = (p[we].mean() / p[~we].mean())
    print(f"{col}: dispersión min={rr.disp.min():.3f} max={rr.disp.max():.3f} media={rr.disp.mean():.3f} (IC95 esperado ~[{1-1.96*np.sqrt(2/780):.2f},{1+1.96*np.sqrt(2/780):.2f}]) | "
          f"corr residuos media={cm[iu].mean():.3f} | finde/sem por grupo min={fw.min():.3f} max={fw.max():.3f} | share finde vs sem max|dif|={np.abs(rr[rr.finde].set_index('k').share - rr[~rr.finde].set_index('k').share).max():.4f}")

print("\n== E. ¿multiplicador por process_date? conteos por tramo de 6 h dentro de la ventana [pd+off, pd+off+24h)")
for t in ['tx', 'cc']:
    off = OFF[t]
    g = q(f"""SELECT process_date d, floor(((epoch(ts)-epoch(process_date::TIMESTAMP))/3600 - {off})/6)::INT b, count(*) n FROM {t} GROUP BY ALL""")
    g['d'] = pd.to_datetime(g.d); p = g.pivot(index='d', columns='b', values='n').reindex(D.index).fillna(0).astype(float)
    rp = p.copy()
    for c in p.columns:
        rp.loc[we, c] = p.loc[we, c] / p.loc[we, c].mean(); rp.loc[~we, c] = p.loc[~we, c] / p.loc[~we, c].mean()
    within = rp[0].corr(rp[3])                       # primer y último tramo del mismo pd
    across = rp[3].corr(rp[0].shift(-1))              # último tramo de d vs primer tramo de d+1 (contiguos en ts)
    print(f"{t}: tramos={list(p.columns)} corr(tramo0,tramo3 mismo pd)={within:.3f}  corr(tramo3 de d, tramo0 de d+1; contiguos en reloj)={across:.3f}")
    # también por ts::DATE: horas 0-5 vs 6-23 del mismo día calendario
print("   (si el multiplicador fuese por ts::DATE, el cruce contiguo tendría corr alta y el intra-pd baja)")

print("\n== F. independencia entre tablas (residuos process_date), rezagos L: corr(a_t, b_{t+L})")
dx = daily('tx', 'process_date', "WHERE status='Declined'").reindex(D.index)
R['tx_decl'] = np.where(we, dx / dx[we].mean(), dx / dx[~we].mean())
ct = daily('cc', 'process_date', "WHERE cat='Transaccional'").reindex(D.index)
R['cc_trx'] = np.where(we, ct / ct[we].mean(), ct / ct[~we].mean())
de = daily('de', 'CAST(ts AS DATE)').reindex(D.index)
print("de finde/sem=%.4f  lun..dom=%s" % (de[we].mean() / de[~we].mean(), (de.groupby(dow).mean() / de[~we].mean()).round(3).tolist()))
R['de'] = de / de.groupby(dow).transform('mean')
print("SE ~ 1/sqrt(n_dias) = %.3f" % (1 / np.sqrt(len(R))))
for a, b in [('tx', 'cc'), ('tx', 'cp'), ('cc', 'cp'), ('tx', 'de'), ('tx_decl', 'cc'), ('tx_decl', 'cc_trx'), ('tx_decl', 'cp'), ('cc', 'sv'), ('cc_trx', 'cc')]:
    print(f"  {a:8s}->{b:7s}: " + ", ".join(f"L{L}={R[a].corr(R[b].shift(-L)):+.3f}" for L in [-1, 0, 1, 2, 3, 7]))
m = q("""WITH c AS (SELECT process_date d, count(*) ncc FROM cc GROUP BY 1), s AS (SELECT process_date d, count(*) nsv FROM sv GROUP BY 1)
         SELECT c.d, ncc, coalesce(nsv,0) nsv FROM c LEFT JOIN s USING(d)""")
for p_ in [0.30, 0.31, 0.32]:
    print(f"  sv==round({p_}*cc) en {np.mean(m.nsv == np.round(m.ncc * p_)):.4f} de {len(m)} días; floor: {np.mean(m.nsv == np.floor(m.ncc * p_)):.4f}")
print("  sv con mismo process_date que su cc:", q("SELECT avg((s.process_date=c.process_date)::INT) same, count(*) n FROM sv s JOIN cc c USING(interaction_id)").to_dict('records'))

print("\n== G. pronóstico (train < 2025-06-17, test >= 2025-06-17)")
cut = pd.Timestamp('2025-06-17'); trm = np.asarray(D.index < cut); tem = ~trm
mape = lambda y, yh: np.mean(np.abs(y - yh) / y) * 100
u = rng.uniform(0.8, 1.2, 10**6)
cs = np.linspace(0.9, 1.05, 301)
print("  piso U(0.8,1.2): pred=media -> %.2f%%; pred MAPE-óptima -> %.2f%%" % (np.mean(np.abs(u - 1) / u) * 100, min(np.mean(np.abs(u - c) / u) * 100 for c in cs)))
for t in ['tx', 'cc', 'cp']:
    s = D[t]; mT = s[trm & we].mean(); mF = s[trm & ~we].mean(); yh = np.where(we, mT, mF)
    y = s.values
    dm = s[trm].groupby(dow[trm]).mean(); yh7 = np.array([dm[k] for k in dow])
    naive7 = s.shift(7).values
    print(f"  {t}: dos medias={mape(y[tem], yh[tem]):.2f}% | 7 medias dow={mape(y[tem], yh7[tem]):.2f}% | naive t-7={mape(y[tem], naive7[tem]):.2f}%")
print("  nowcast intradía: total del pd estimado con el conteo de las primeras 6 h de su ventana (factor de escala de train)")
for t in ['tx', 'cc', 'cp']:
    off = OFF[t]
    g = q(f"""SELECT process_date d, count(*) FILTER (WHERE (epoch(ts)-epoch(process_date::TIMESTAMP))/3600 < {off}+6) n6, count(*) n FROM {t} GROUP BY 1""")
    g['d'] = pd.to_datetime(g.d); g = g.set_index('d').reindex(D.index)
    k = g.n[trm].sum() / g.n6[trm].sum()
    print(f"    {t}: factor={k:.3f} MAPE test nowcast 6h={mape(g.n[tem].values, k * g.n6[tem].values):.2f}%  (vs dos medias {mape(D[t].values[tem], np.where(we, D[t][trm & we].mean(), D[t][trm & ~we].mean())[tem]):.2f}%)")
