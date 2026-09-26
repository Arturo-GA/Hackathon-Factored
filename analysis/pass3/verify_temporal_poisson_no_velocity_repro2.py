"""Verificación independiente (ronda 2) de 'temporal_poisson_no_velocity'.
Uso: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_temporal_poisson_no_velocity_repro2.py [A B C D E F]
A) conteo por producto (universo pr completo): Poisson GOF, dispersión, igualdad de tasas por ptype/país/moneda/año de apertura/segmento (test LR Poisson)
B) conteo producto-mes (hora local = UTC-6, 35 meses completos, universo = productos Active incl. 0 tx)
C) intervalos dentro de producto (datos completos): CV, cuantiles normalizados vs exponencial y vs nulo exacto (n puntos uniformes),
   ráfagas vs esperado analítico y vs permutación de ts entre tx (mantiene el calendario global); también intervalos por cliente
D) heterogeneidad por cliente: var_obs/var_binomial + z; dispersión multinomial hora (24), día de semana (7), estado, canal; controles positivos
E) fraude: agrupamiento por cliente/producto/día, Markov de estado y fraude, qué pasa tras un fraude (siguiente tx, lag 2, tx restantes obs vs esperado)
F) calendario global: intensidad por día de semana (local), dispersión del volumen diario, meses
"""
import sys, time
import duckdb, numpy as np, pandas as pd
from scipy import stats
from scipy.optimize import brentq

pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
SECTIONS = set(sys.argv[1:]) or set('ABCDEF')
T0 = time.time()
# ventana: [2023-06-17 00:00, 2026-06-18 00:00) hora local (UTC-6) = [06:00 UTC, 06:00 UTC)
W0 = pd.Timestamp('2023-06-17 06:00:00'); W1 = pd.Timestamp('2026-06-18 06:00:00')
T = (W1 - W0).total_seconds()  # 1097 días
LOC = "(ts - INTERVAL 6 HOUR)"


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def lr_poisson(df, grp, col='n'):
    g = df.groupby(grp)[col].agg(['count', 'sum', 'mean', 'var'])
    lam = df[col].sum() / len(df)
    G = 2 * (g['sum'] * np.log(g['sum'] / (g['count'] * lam))).sum()
    dof = len(g) - 1
    g['disp'] = g['var'] / g['mean']
    return g, G, dof, stats.chi2.sf(G, dof), g['mean'].max() / g['mean'].min()


if 'A' in SECTIONS:
    print("== A. tx por producto ==")
    d = q("""WITH a AS (SELECT product_id, count(*) n FROM tx GROUP BY 1)
      SELECT p.product_id, p.ptype, p.pstatus, p.currency, year(p.opened) oy, c.country ccountry, c.segment,
             coalesce(a.n, 0)::INT n
      FROM pr p LEFT JOIN a USING(product_id) LEFT JOIN cu c ON c.customer_id = p.customer_id""")
    print(d.groupby('pstatus').n.agg(prods='count', con_tx=lambda x: int((x > 0).sum()), mean='mean', max='max'))
    act = d[d.pstatus == 'Active'].copy()
    n = act.n.values; N = len(n); lam = n.mean(); v = n.var(ddof=1)
    print(f"Active: {N} prods, con tx={int((n > 0).sum())}, ceros obs={int((n == 0).sum())} esp={N * stats.poisson.pmf(0, lam):.2f}")
    print(f"  media={lam:.4f} var={v:.4f} disp={v / lam:.4f} (SE {np.sqrt(2 / (N - 1)):.4f}, z={(v / lam - 1) / np.sqrt(2 / (N - 1)):.2f}) min={n.min()} max={n.max()}")
    nt = n[n > 0]
    print(f"  solo con tx: {len(nt)} media={nt.mean():.4f} var={nt.var(ddof=1):.4f} disp={nt.var(ddof=1) / nt.mean():.4f} min={nt.min()} max={nt.max()}")
    obs = np.bincount(n); k = np.arange(len(obs)); ex = stats.poisson.pmf(k, lam) * N
    # agrupar colas para esperado >= 5
    lo = int(np.argmax(np.cumsum(ex) >= 5)); hi = int(len(ex) - 1 - np.argmax(np.cumsum(ex[::-1]) >= 5))
    o = np.r_[obs[:lo + 1].sum(), obs[lo + 1:hi], obs[hi:].sum()]
    e = np.r_[ex[:lo + 1].sum(), ex[lo + 1:hi], N - ex[:hi].sum()]
    chi = ((o - e) ** 2 / e).sum(); dof = len(o) - 2
    print(f"  GOF Poisson: chi2={chi:.1f} gl={dof} p={stats.chi2.sf(chi, dof):.3f}; P(n>=33) esp={N * stats.poisson.sf(32, lam):.2f}, obs={(n >= 33).sum()}")
    # alternativa binomial/fija: si n fuese fijo o binomial la dispersión sería <1; NB => >1
    for grp in ['ptype', 'currency', 'ccountry', 'segment', 'oy']:
        g, G, dof, p, rr = lr_poisson(act, grp)
        print(f"  por {grp}: LR={G:.1f} gl={dof} p={p:.3f}; razón máx/mín de medias={rr:.4f}")
        if grp in ('ptype', 'oy'):
            print(g.round(3).to_string())
    print(f"[A {time.time() - T0:.0f}s]")

if 'B' in SECTIONS:
    print("\n== B. conteo producto-mes (local, jul-2023..may-2026 = 35 meses, universo Active) ==")
    Nact = con.execute("SELECT count(*) FROM pr WHERE pstatus='Active'").fetchone()[0]
    r = q(f"""WITH m AS (SELECT product_id, date_trunc('month', {LOC}) mo, count(*) k FROM tx
          WHERE {LOC} >= TIMESTAMP '2023-07-01' AND {LOC} < TIMESTAMP '2026-06-01' GROUP BY ALL)
          SELECT count(*) cells_nz, sum(k) sk, sum(k*k) sk2, max(k) kmax FROM m""")
    cells = Nact * 35; sk = float(r.sk[0]); sk2 = float(r.sk2[0])
    mean = sk / cells; var = (sk2 - sk * sk / cells) / (cells - 1)
    print(f"celdas={cells} media={mean:.4f} var={var:.4f} disp={var / mean:.5f} (SE~{np.sqrt(2 / cells):.5f}) kmax={int(r.kmax[0])}")
    mt = q(f"""SELECT date_trunc('month', {LOC}) mo, count(*) n FROM tx
          WHERE {LOC} >= TIMESTAMP '2023-07-01' AND {LOC} < TIMESTAMP '2026-06-01' GROUP BY 1 ORDER BY 1""")
    mt['days'] = mt.mo.dt.days_in_month; mt['per_day'] = mt.n / mt.days
    # varianza entre medias mensuales por producto (mezcla) -> exceso de dispersión esperado
    mu = mt.n / Nact
    print(f"totales mensuales: tx/día min={mt.per_day.min():.0f} max={mt.per_day.max():.0f} CV={mt.per_day.std() / mt.per_day.mean():.4f}; "
          f"exceso de disp. esperado por mezcla de meses={mu.var(ddof=0) / mu.mean():.5f}")
    print(f"[B {time.time() - T0:.0f}s]")

if 'C' in SECTIONS:
    print("\n== C. intervalos entre tx del mismo producto (datos completos) ==")
    hist = q("SELECT n, count(*) k FROM (SELECT product_id, count(*) n FROM tx GROUP BY 1) GROUP BY 1 ORDER BY 1")
    nn = hist.n.values.astype(float); kk = hist.k.values.astype(float)
    gap_sql = """SELECT epoch({ts}) - epoch(lag({ts}) OVER w) gap, count(*) OVER (PARTITION BY {pid}) n
                 FROM {src} WINDOW w AS (PARTITION BY {pid} ORDER BY {ts}{tie})"""
    agg_sql = """SELECT count(gap) ng, avg(gap)/86400 mean_d, stddev(gap)/avg(gap) cv,
        sum((gap=0)::INT) s0, sum((gap<60)::INT) s60, sum((gap<3600)::INT) s3600, sum((gap<86400)::INT) s86400,
        quantile_cont(gap*n/{T}, [0.01,0.1,0.25,0.5,0.75,0.9,0.99]) zq FROM g WHERE gap IS NOT NULL"""
    con.execute("CREATE OR REPLACE TEMP TABLE g AS " + gap_sql.format(ts='ts', pid='product_id', src='tx', tie=', transaction_id'))
    ob = q(agg_sql.format(T=T))
    con.execute("DROP TABLE g")
    # permutación: se reasignan los ts entre todas las tx (conserva n de cada producto y el calendario global)
    con.execute("""CREATE OR REPLACE TEMP TABLE pa AS SELECT hash(product_id) ph, hash(customer_id) ch,
                   row_number() OVER (ORDER BY hash(transaction_id || 'a')) rn FROM tx""")
    con.execute("CREATE OR REPLACE TEMP TABLE pb AS SELECT ts, row_number() OVER (ORDER BY hash(transaction_id || 'b')) rn FROM tx")
    con.execute("CREATE OR REPLACE TEMP TABLE perm AS SELECT pa.ph, pa.ch, pb.ts FROM pa JOIN pb USING(rn)")
    con.execute("DROP TABLE pa; DROP TABLE pb")
    con.execute("CREATE OR REPLACE TEMP TABLE g AS " + gap_sql.format(ts='ts', pid='ph', src='perm', tie=''))
    pm = q(agg_sql.format(T=T))
    con.execute("DROP TABLE g")
    print(f"intervalos: obs={int(ob.ng[0])} | media obs={ob.mean_d[0]:.2f} d perm={pm.mean_d[0]:.2f} d | CV obs={ob.cv[0]:.4f} perm={pm.cv[0]:.4f}")
    print("umbral   obs   esp_uniforme  obs/esp  perm(calendario)  obs/perm   (% de intervalos obs)")
    for s, col in [(0.5, 's0'), (60, 's60'), (3600, 's3600'), (86400, 's86400')]:
        e = (kk * (nn - 1) * (1 - (1 - s / T) ** nn)).sum()
        o = int(ob[col][0]); p_ = int(pm[col][0])
        print(f"{col:7s} {o:7d} {e:12.1f} {o / e:8.3f} {p_:10d} {o / max(p_, 1):14.3f}   ({100 * o / ob.ng[0]:.4f}%)")
    # cuantiles del intervalo normalizado z = gap*n/T : exp(1) vs nulo exacto (Beta(1,n) escalado)
    w = kk * (nn - 1)
    Fnull = lambda x: (w * (1 - np.clip(1 - x / nn, 0, None) ** nn)).sum() / w.sum()
    print("q      obs     perm    nulo_uniforme_n_finito   exp(1)")
    for i, p in enumerate([0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99]):
        xn = brentq(lambda x: Fnull(x) - p, 1e-9, 40)
        print(f"{p:<5} {ob.zq[0][i]:7.4f} {pm.zq[0][i]:7.4f} {xn:12.4f} {-np.log(1 - p):16.4f}")
    # intervalos por cliente (entre todos sus productos)
    csql = """WITH g AS (SELECT epoch({ts}) - epoch(lag({ts}) OVER (PARTITION BY {cid} ORDER BY {ts})) gap FROM {src})
              SELECT count(gap) ng, sum((gap=0)::INT) s0, sum((gap<60)::INT) s60, sum((gap<3600)::INT) s3600,
                     sum((gap<86400)::INT) s86400, stddev(gap)/avg(gap) cv FROM g"""
    co = q(csql.format(ts='ts', cid='customer_id', src='tx')); cp = q(csql.format(ts='ts', cid='ch', src='perm'))
    print("cliente obs :", co.round(4).to_dict('records')[0])
    print("cliente perm:", cp.round(4).to_dict('records')[0])
    con.execute("DROP TABLE perm")
    print(f"[C {time.time() - T0:.0f}s]")

if 'D' in SECTIONS:
    print("\n== D. heterogeneidad por cliente (clientes con >=10 tx) ==")
    c = q(f"""SELECT customer_id, count(*) n,
        sum((isodow(process_date) >= 6)::INT) wk, sum((hour({LOC}) < 6)::INT) night,
        sum((status='Declined')::INT) decl, sum((status='Reversed')::INT) rev, sum((status='Pending')::INT) pend,
        sum(fraud::INT) fr, sum(coalesce(fscore >= 50, false)::INT) fs50,
        sum((channel IN ('App','Web'))::INT) dig, sum((channel='ATM')::INT) atm,
        sum((ttype='Purchase')::INT) purch, sum((currency='USD')::INT) usd
        FROM tx GROUP BY 1""")
    x = c[c.n >= 10]; Nc = len(x)
    print(f"clientes con tx={len(c)}, con >=10 tx={Nc}, n medio={x.n.mean():.1f}")
    rows = []
    for kcol in ['wk', 'night', 'decl', 'rev', 'pend', 'fr', 'fs50', 'dig', 'atm', 'purch', 'usd']:
        p = c[kcol].sum() / c.n.sum(); e = x.n * p
        num = ((x[kcol] - e) ** 2).sum(); den = (e * (1 - p)).sum()
        chi = (((x[kcol] - e) ** 2) / (e * (1 - p))).sum(); dof = Nc - 1
        tau2 = (num - den) / (x.n * (x.n - 1)).sum()
        rows.append(dict(var=kcol, p=round(p, 5), ratio=round(num / den, 4), chi2_df=round(chi / dof, 4),
                         z=round((chi - dof) / np.sqrt(2 * dof), 1),
                         sd_entre_clientes_pp=round(100 * np.sqrt(max(tau2, 0)), 3)))
    print(pd.DataFrame(rows).to_string(index=False))

    def multinom(expr, label, where="TRUE"):
        r = q(f"""WITH b AS (SELECT customer_id, {expr} b FROM tx WHERE {where}),
            pk AS (SELECT b, count(*)::DOUBLE / (SELECT count(*) FROM b) p FROM b GROUP BY 1),
            cb AS (SELECT customer_id, b, count(*) o FROM b GROUP BY ALL),
            cs AS (SELECT customer_id, sum(o) n, sum(o*o/p) s FROM cb JOIN pk USING(b) GROUP BY 1)
            SELECT n, s/n - n chi FROM cs WHERE n >= 10""")
        pk = q(f"WITH b AS (SELECT {expr} b FROM tx WHERE {where}) SELECT b, count(*)::DOUBLE/(SELECT count(*) FROM b) p FROM b GROUP BY 1").p.values
        K = len(pk); var_c = 2 * (K - 1) + ((1 / pk).sum() - K * K - 2 * K + 2) / r.n.values
        ratio = r.chi.sum() / (len(r) * (K - 1)); z = (r.chi.sum() - len(r) * (K - 1)) / np.sqrt(var_c.sum())
        print(f"  multinomial {label:22s} K={K:2d} clientes={len(r)} chi2/gl={ratio:.4f} z={z:.1f}")
    print("dispersión multinomial por cliente (1 = sin preferencia individual):")
    multinom(f"hour({LOC})", "hora local (24)")
    multinom("isodow(process_date)", "día de semana (7)")
    multinom("month(process_date)", "mes del año (12)")
    multinom("status", "estado (4)")
    multinom("channel", "canal (6)")
    multinom("coalesce(code,'NA')", "código (5+NA)")
    multinom("ttype", "ttype (control +)")
    print(f"[D {time.time() - T0:.0f}s]")

if 'E' in SECTIONS:
    print("\n== E. fraude ==")
    c = q("SELECT customer_id, count(*) n, sum(fraud::INT) fr FROM tx GROUP BY 1")
    p = c.fr.sum() / c.n.sum()
    print(f"tx fraude={int(c.fr.sum())} p={p:.6f}")
    print("clientes por nº de fraudes obs:", c.fr.value_counts().sort_index().to_dict())
    print("  esp Poisson :", {k: round(float(stats.poisson.pmf(k, c.n * p).sum()), 1) for k in range(4)},
          ">=2:", round(float(stats.poisson.sf(1, c.n * p).sum()), 1))
    print("  esp binomial:", {k: round(float(stats.binom.pmf(k, c.n, p).sum()), 1) for k in range(4)},
          ">=2:", round(float(stats.binom.sf(1, c.n, p).sum()), 1))
    pf = q("SELECT n, fr, count(*) k FROM (SELECT product_id, count(*) n, sum(fraud::INT) fr FROM tx GROUP BY 1) GROUP BY ALL")
    nb = pf.groupby('n').k.sum()
    ge1 = int(pf[pf.fr >= 1].k.sum()); ge2 = int(pf[pf.fr >= 2].k.sum())
    print(f"productos con >=1 fraude obs={ge1} esp={float((nb * stats.binom.sf(0, nb.index, p)).sum()):.1f}; "
          f">=2 obs={ge2} esp={float((nb * stats.binom.sf(1, nb.index, p)).sum()):.1f}")
    dd = q("SELECT process_date, count(*) n, sum(fraud::INT) f FROM tx GROUP BY 1")
    pdn = dd.f.sum() / dd.n.sum()
    print(f"fraude diario: días={len(dd)} disp bruta={dd.f.var() / dd.f.mean():.3f} "
          f"disp condicionada al volumen={((dd.f - dd.n * pdn) ** 2).sum() / (dd.n * pdn * (1 - pdn)).sum():.3f}")
    # secuencia dentro de producto
    con.execute("""CREATE OR REPLACE TEMP TABLE sq AS SELECT fraud, status, coalesce(fscore >= 50, false) fs50,
        lag(fraud) OVER w pf, lag(fraud, 2) OVER w pf2, lag(status) OVER w ps,
        epoch(lead(ts) OVER w) - epoch(ts) ngap, lead(ts) OVER w IS NULL is_last,
        max(fraud::INT) OVER (PARTITION BY product_id) prod_has_fraud,
        count(*) OVER (PARTITION BY product_id) n, row_number() OVER w rn,
        percent_rank() OVER (ORDER BY ts) F
        FROM tx WINDOW w AS (PARTITION BY product_id ORDER BY ts, transaction_id)""")
    t = q("SELECT ps, status, count(*) c FROM sq WHERE ps IS NOT NULL GROUP BY ALL").pivot(index='ps', columns='status', values='c')
    print("P(status | status previo del mismo producto):"); print(t.div(t.sum(axis=1), axis=0).round(4).to_string())
    print("  n por fila:", t.sum(axis=1).astype(int).to_dict())
    for lagc in ['pf', 'pf2']:
        r = q(f"""SELECT {lagc} prev_fraud, count(*) m, sum(fraud::INT) f, sum((status='Declined')::INT) dcl, sum(fs50::INT) f50
                  FROM sq WHERE {lagc} IS NOT NULL GROUP BY 1 ORDER BY 1""")
        for _, rr in r.iterrows():
            lo, hi = wilson(rr.f, rr.m); lo2, hi2 = wilson(rr.dcl, rr.m)
            print(f"  {lagc}={rr.prev_fraud!s:5s} m={int(rr.m):8d} P(fraude)={rr.f / rr.m:.5f} [{lo:.5f},{hi:.5f}] (k={int(rr.f)}) "
                  f"P(Declined)={rr.dcl / rr.m:.4f} [{lo2:.4f},{hi2:.4f}] (k={int(rr.dcl)}) P(fs>=50)={rr.f50 / rr.m:.5f}")
    r = q("""SELECT CASE WHEN fraud THEN 'fraude' WHEN prod_has_fraud=1 THEN 'no fraude, prod c/fraude' ELSE 'no fraude, prod s/fraude' END grp,
             count(*) m, avg(is_last::INT) share_last, count(ngap) with_next, median(ngap)/86400 med_next_d, avg(ngap)/86400 mean_next_d,
             avg(n) n_medio, sum(n - rn) obs_after, sum((n - 1) * (1 - F)) exp_after_cal, sum((n-1)*(1 - F)) FILTER (WHERE TRUE) x
             FROM sq GROUP BY 1 ORDER BY 1""")
    r['obs/esp_after'] = r.obs_after / r.exp_after_cal
    print(r.drop(columns=['x']).round(4).to_string(index=False))
    r = q("SELECT fraud, count(*) m, avg(is_last::INT) sl, median(ngap)/86400 md, avg(n) nm, sum(n-rn) oa, sum((n-1)*(1-F)) ea FROM sq GROUP BY 1")
    print("todas las no-fraude vs fraude:"); print(r.round(4).to_string(index=False))
    con.execute("DROP TABLE sq")
    print("productos con fraude por pstatus:", q("SELECT p.pstatus, count(*) c FROM (SELECT DISTINCT product_id FROM tx WHERE fraud) f JOIN pr p USING(product_id) GROUP BY 1").values.tolist())
    print(f"[E {time.time() - T0:.0f}s]")

if 'F' in SECTIONS:
    print("\n== F. calendario global (hora local UTC-6 = process_date) ==")
    dd = q("SELECT process_date d, isodow(process_date) dow, count(*) n FROM tx GROUP BY ALL")
    w = dd.groupby('dow').n.agg(['count', 'mean', 'std'])
    w['poisson_sd'] = np.sqrt(w['mean']); w['rel_int'] = w['mean'] / dd.n.mean()
    print(w.round(1).to_string())
    wk = dd[dd.dow <= 5].n; we = dd[dd.dow >= 6].n
    print(f"lun-vie media={wk.mean():.0f} sd={wk.std():.0f}; sáb-dom media={we.mean():.0f} sd={we.std():.0f}; razón fin de semana/hábil={we.mean() / wk.mean():.3f}; "
          f"% tx en fin de semana={100 * we.sum() / dd.n.sum():.2f}% (uniforme 28,6%)")
    dd['res'] = dd.n / dd.groupby('dow').n.transform('mean')
    print("días con menor volumen relativo a su día de semana:")
    print(dd.nsmallest(8, "res")[["d", "dow", "n", "res"]].to_string(index=False))
    print(f"residuo relativo diario: sd={dd.res.std():.3f}; percentiles 1/50/99 = {np.percentile(dd.res, [1, 50, 99]).round(3)}")
    # ¿el shock diario es común a los países?
    dc = q("SELECT process_date d, country, count(*) n FROM tx GROUP BY ALL").pivot(index='d', columns='country', values='n')
    dc = dc[[k for k in dc.columns if dc[k].sum() > 100000]]
    dc['dow'] = pd.to_datetime(dc.index).dayofweek
    res = dc.drop(columns='dow').div(dc.groupby('dow').transform('mean').drop(columns='dow', errors='ignore'))
    print("correlación entre países del residuo diario (volumen/día de semana medio):")
    print(res.corr().round(3).to_string())
    h, edges = np.histogram(dd.res, bins=8, range=(0.8, 1.2))
    print(f"residuo diario min={dd.res.min():.4f} max={dd.res.max():.4f}; histograma 8 bins en [0,8;1,2]: {h.tolist()} "
          f"(uniforme => ~{len(dd) / 8:.0f} c/u; sd U(0,8;1,2)={0.4 / np.sqrt(12):.4f})")
    print(f"[F {time.time() - T0:.0f}s]")

if 'G' in SECTIONS:
    print("\n== G. detalle: estado de la tx siguiente/anterior a un fraude (¿4,0% vs 5,0% es azar?) ==")
    con.execute("""CREATE OR REPLACE TEMP TABLE sq2 AS SELECT fraud, coalesce(fscore >= 50, false) fs50, year(process_date) yr,
        lead(status) OVER w ns, lag(status) OVER w ps, lead(ttype) OVER w nt, lead(code) OVER w nc
        FROM tx WINDOW w AS (PARTITION BY product_id ORDER BY ts, transaction_id)""")
    for col, lab in [('ns', 'siguiente'), ('ps', 'anterior')]:
        t = q(f"SELECT fraud, {col} st, count(*) c FROM sq2 WHERE {col} IS NOT NULL GROUP BY ALL").pivot(index='fraud', columns='st', values='c')
        print(f"estado de la tx {lab} (filas: la tx actual es fraude?):"); print(t.div(t.sum(axis=1), axis=0).round(4).to_string())
        print("   n:", t.sum(axis=1).astype(int).to_dict())
        k = int(t.loc[True, 'Declined']); m = int(t.loc[True].sum()); p0 = t.loc[False, 'Declined'] / t.loc[False].sum()
        print(f"   binomial Declined|fraude: k={k} m={m} esp={m * p0:.1f} p_bilateral={stats.binomtest(k, m, p0).pvalue:.4f} RR={k / m / p0:.3f}")
    r = q("""SELECT fs50, count(ns) m, avg((ns='Declined')::INT) p_next_decl FROM sq2 WHERE ns IS NOT NULL GROUP BY 1""")
    print("P(siguiente Declined | fscore>=50):", r.round(4).to_dict('records'))
    r = q("""SELECT yr, count(*) m, sum((ns='Declined')::INT) k FROM sq2 WHERE fraud AND ns IS NOT NULL GROUP BY 1 ORDER BY 1""")
    r['p'] = r.k / r.m; print("P(siguiente Declined | fraude) por año:", r.round(4).to_dict('records'))
    t = q("SELECT fraud, nt, count(*) c FROM sq2 WHERE nt IS NOT NULL GROUP BY ALL").pivot(index='fraud', columns='nt', values='c')
    print("ttype de la tx siguiente:"); print(t.div(t.sum(axis=1), axis=0).round(4).to_string())
    con.execute("DROP TABLE sq2")
    # nulo por remuestreo: 2000 subconjuntos aleatorios de 4.003 tx con siguiente -> distribución de P(siguiente Declined)
    s = q("""SELECT (lead(status) OVER w = 'Declined')::INT y FROM tx WINDOW w AS (PARTITION BY product_id ORDER BY ts, transaction_id)
             QUALIFY lead(status) OVER w IS NOT NULL USING SAMPLE 400000 ROWS (reservoir, 5)""").y.values
    rng = np.random.default_rng(1)
    sims = np.array([s[rng.integers(0, len(s), 4003)].mean() for _ in range(2000)])
    print(f"remuestreo (m=4003): media={sims.mean():.4f} sd={sims.std():.4f}; P(<=0,0402)={np.mean(sims <= 0.0402):.4f}")
    print("\n-- Pending por producto (¿subdispersión?) --")
    pp = q("SELECT n, pend, count(*) k FROM (SELECT product_id, count(*) n, sum((status='Pending')::INT) pend FROM tx GROUP BY 1) GROUP BY ALL")
    pP = (pp.pend * pp.k).sum() / (pp.n * pp.k).sum()
    for kk_ in range(4):
        o = int(pp[pp.pend == kk_].k.sum()); e = float((pp.k * stats.binom.pmf(kk_, pp.n, pP)).sum())
        print(f"  productos con {kk_} Pending: obs={o} esp_binom={e:.1f}")
    print("P(Pending) por año:", q("SELECT year(process_date) yr, avg((status='Pending')::INT) p FROM tx GROUP BY 1 ORDER BY 1").round(4).to_dict('records'))
    print(f"[G {time.time() - T0:.0f}s]")
