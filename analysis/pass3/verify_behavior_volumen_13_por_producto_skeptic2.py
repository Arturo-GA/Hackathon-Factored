"""Verificador escéptico (reintento): 'El volumen transaccional es 13 tx por producto activo (Poisson) y nada más lo explica'.

Ángulos NUEVOS de refutación (además de reproducir las cifras núcleo):
 A. Cifras núcleo: tx/producto Active, dispersión, ceros, tx en no-Active, clientes sin activos.
 B. Mecanismo: multiplicidad producto-día (¿tope de 1 tx/día? ¿ráfagas?) vs asignación multinomial independiente
    con el volumen diario observado; huecos entre tx consecutivas del mismo producto vs simulación.
 C. ¿'Nada más lo explica' también MARGINALMENTE a nivel cliente? El #productos (nprod, nact) ¿depende del perfil
    (segmento, ingreso, país, edad, cstatus...)? Si sí, el perfil predice el volumen vía nact (mediación).
    GBM held-out (R² con IC95 bootstrap) para nact y para ntx SIN nact.
 D. ¿Qué productos quedan Active (y por tanto con tx)? P(Active) vs atributos.
 E. 'Volumen' en MONTO (USD-eq con tasas fijas ARS 350 / COP 4000): ¿lo explica solo nact o también la mezcla de ptype?
 F. Los 2 productos Active sin tx.
 G. Utilidad para el flujo de tarjetas: densidad reciente de compras por tarjeta activa; tarjetas Blocked sin historial.
 H. Nivel cliente: ntx por nact, Gini observado vs simulado. I. Correlación entre conteos de productos del mismo cliente.
Ejecutar: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_behavior_volumen_13_por_producto_skeptic2.py [secciones, ej. ABC]
"""
import sys
import duckdb
import numpy as np
import pandas as pd
from scipy import stats

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
SECS = sys.argv[1] if len(sys.argv) > 1 else "ABCDEFGHI"

con = duckdb.connect("data/analysis.duckdb", read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()
F = lambda s: con.execute(s).fetchall()
rng = np.random.default_rng(11)
K_FX = "CASE currency WHEN 'ARS' THEN 350.0 WHEN 'COP' THEN 4000.0 ELSE 1.0 END"

con.execute("""CREATE TEMP TABLE pc AS SELECT p.product_id, p.customer_id, p.ptype, p.pstatus, p.opened, p.expires, p.currency,
     p.opening_channel, p.app, coalesce(t.n,0) n
   FROM pr p LEFT JOIN (SELECT product_id, count(*) n FROM tx GROUP BY 1) t USING(product_id)""")
KACT = F("SELECT count(*) FROM pc WHERE pstatus='Active'")[0][0]

if "A" in SECS:
    print("=== A. Cifras núcleo ===")
    print(Q("""SELECT count(*) ntx, count(DISTINCT transaction_id) ids, count(*) FILTER (WHERE product_id IS NULL) pid_nulo,
          count(*) FILTER (WHERE product_id NOT IN (SELECT product_id FROM pr)) pid_inexistente FROM tx""").to_string(index=False))
    print(Q("SELECT pstatus, count(*) nprod, sum(n) ntx, count(*) FILTER (WHERE n>0) con_tx FROM pc GROUP BY 1 ORDER BY 1").to_string(index=False))
    N, m, v, z0, mx = F("SELECT count(*), avg(n), var_samp(n), count(*) FILTER (WHERE n=0), max(n) FROM pc WHERE pstatus='Active'")[0]
    se = np.sqrt(2 / (N - 1))
    print(f"Active N={N:,} media={m:.4f} var={v:.4f} disp={v/m:.4f} (z vs 1 = {(v/m-1)/se:+.2f}) ceros={z0} (esperado {N*np.exp(-m):.2f}) max={mx}")
    print(Q("""SELECT ptype, count(*) k, round(avg(n),3) media, round(var_samp(n)/avg(n),3) disp FROM pc WHERE pstatus='Active' GROUP BY 1 ORDER BY 2 DESC""").to_string(index=False))

if "B" in SECS:
    print("\n=== B1. Multiplicidad producto-día (process_date) vs multinomial independiente ===")
    h = Q("SELECT c, count(*) k FROM (SELECT product_id, process_date, count(*) c FROM tx GROUP BY 1,2) GROUP BY 1 ORDER BY 1")
    nd = Q("SELECT process_date, count(*) n FROM tx GROUP BY 1")["n"].values
    exp = {}
    for c in h.c.values:
        exp[c] = float(np.sum(KACT * stats.binom.pmf(c, nd, 1.0 / KACT)))
    h["esperado"] = h.c.map(exp).round(1)
    h["obs/esp"] = (h.k / h.esperado).round(4)
    print(h.to_string(index=False))

    print("\n=== B2. Huecos entre tx consecutivas del mismo producto (muestra 1/4 de productos) vs simulación ===")
    g = Q("""SELECT pid, e FROM (SELECT dense_rank() OVER (ORDER BY product_id) pid, epoch(ts) e FROM tx WHERE hash(product_id) % 4 = 0)""")
    g = g.sort_values(["pid", "e"])
    pid = g.pid.values; e = g.e.values.astype(float)
    same = pid[1:] == pid[:-1]
    gaps_obs = (e[1:] - e[:-1])[same]
    # simulación: mismos n por producto, tiempos sorteados de la distribución empírica diaria (patrón semanal incluido)
    days = Q("SELECT epoch(min(ts)) t0 FROM tx")["t0"].values[0]
    dd = Q("SELECT process_date d, count(*) n FROM tx GROUP BY 1 ORDER BY 1")
    p_day = dd.n.values / dd.n.values.sum()
    counts = np.bincount(pid)[1:] if pid.min() == 1 else np.bincount(pid)
    counts = counts[counts > 0]
    tot = counts.sum()
    dsel = rng.choice(len(dd), size=tot, p=p_day)
    tsim = days + dsel * 86400.0 + rng.uniform(0, 86400.0, tot)
    psim = np.repeat(np.arange(len(counts)), counts)
    o = np.lexsort((tsim, psim)); tsim = tsim[o]; psim = psim[o]
    s2 = psim[1:] == psim[:-1]
    gaps_sim = (tsim[1:] - tsim[:-1])[s2]
    edges = [0, 60, 3600, 86400, 7 * 86400, 30 * 86400, 90 * 86400, 365 * 86400, 1e12]
    labs = ["<1min", "1-60min", "1-24h", "1-7d", "7-30d", "30-90d", "90-365d", ">=365d"]
    ho = np.histogram(gaps_obs, edges)[0]; hs = np.histogram(gaps_sim, edges)[0]
    print(pd.DataFrame({"hueco": labs, "obs": ho, "sim": hs, "obs/sim": np.round(ho / np.maximum(hs, 1), 3)}).to_string(index=False))
    print(f"productos en muestra={len(counts):,} tx={tot:,}; mediana hueco obs={np.median(gaps_obs)/86400:.1f} d vs sim={np.median(gaps_sim)/86400:.1f} d; "
          f"CV huecos obs={gaps_obs.std()/gaps_obs.mean():.3f} sim={gaps_sim.std()/gaps_sim.mean():.3f}")
    del g, pid, e, gaps_obs, tsim, psim, gaps_sim

if "C" in SECS or "E" in SECS:
    cst = Q(f"""SELECT c.customer_id, c.segment, c.country, c.cstatus, c.gender, c.income, c.credit_score, c.occupation,
          c.marital_status, c.education_level, c.detected_accent, c.mkt::INT mkt,
          date_diff('day', DATE '2000-01-01', c.registration_date::DATE) reg_d, date_diff('day', c.dob, DATE '2026-06-17') edad_d,
          coalesce(p.nprod,0) nprod, coalesce(p.nact,0) nact, coalesce(t.ntx,0) ntx, coalesce(t.usd,0) usd,
          coalesce(p.a_ca,0) a_ca, coalesce(p.a_cc,0) a_cc, coalesce(p.a_tc,0) a_tc, coalesce(p.a_td,0) a_td,
          coalesce(p.a_pp,0) a_pp, coalesce(p.a_ph,0) a_ph, coalesce(p.a_in,0) a_in, coalesce(p.a_se,0) a_se
        FROM cu c
        LEFT JOIN (SELECT customer_id, count(*) nprod, count(*) FILTER (WHERE pstatus='Active') nact,
             count(*) FILTER (WHERE pstatus='Active' AND ptype='Cuenta Ahorro') a_ca,
             count(*) FILTER (WHERE pstatus='Active' AND ptype='Cuenta Corriente') a_cc,
             count(*) FILTER (WHERE pstatus='Active' AND ptype='Tarjeta Crédito') a_tc,
             count(*) FILTER (WHERE pstatus='Active' AND ptype='Tarjeta Débito') a_td,
             count(*) FILTER (WHERE pstatus='Active' AND ptype='Préstamo Personal') a_pp,
             count(*) FILTER (WHERE pstatus='Active' AND ptype='Préstamo Hipotecario') a_ph,
             count(*) FILTER (WHERE pstatus='Active' AND ptype='Inversión') a_in,
             count(*) FILTER (WHERE pstatus='Active' AND ptype='Seguro') a_se
           FROM pr GROUP BY 1) p USING(customer_id)
        LEFT JOIN (SELECT customer_id, count(*) ntx, sum(amount / {K_FX}) usd FROM tx GROUP BY 1) t USING(customer_id)""")

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression


def r2_ci(y, pred, base, B=500):
    """R² held-out del modelo vs baseline (predicción constante u otra), con IC95 bootstrap sobre clientes de test."""
    se_m = (y - pred) ** 2; se_b = (y - base) ** 2
    r = 1 - se_m.sum() / se_b.sum()
    idx = [rng.integers(0, len(y), len(y)) for _ in range(B)]
    bs = np.array([1 - se_m[i].sum() / se_b[i].sum() for i in idx])
    return r, np.percentile(bs, 2.5), np.percentile(bs, 97.5)


if "C" in SECS:
    print("\n=== C1. Distribución de #productos por cliente vs Poisson (asignación aleatoria de productos a clientes) ===")
    for col in ["nprod", "nact"]:
        x = cst[col].values; mu = x.mean(); var = x.var(ddof=1)
        vc = np.bincount(x)
        exp = len(x) * stats.poisson.pmf(np.arange(len(vc)), mu)
        ob, eb, ao, ae = [], [], 0.0, 0.0
        for o_, e_ in zip(vc, exp):
            ao += o_; ae += e_
            if ae >= 10:
                ob.append(ao); eb.append(ae); ao = ae = 0.0
        ob[-1] += ao; eb[-1] += ae + len(x) * stats.poisson.sf(len(vc) - 1, mu)
        ob, eb = np.array(ob), np.array(eb)
        chi2 = ((ob - eb) ** 2 / eb).sum()
        print(f"{col}: media={mu:.4f} var={var:.4f} disp={var/mu:.4f}; P(0) obs={np.mean(x==0):.4f} vs Poisson={np.exp(-mu):.4f}; "
              f"GOF chi2={chi2:.1f} df={len(ob)-2} p={stats.chi2.sf(chi2, len(ob)-2):.3f}; max={x.max()}")
    print("fracción Active entre productos:", round(F("SELECT avg((pstatus='Active')::INT) FROM pr")[0][0], 4),
          "| nact/nprod medio (clientes con productos):", round((cst.nact.sum() / cst.nprod.sum()), 4))

    print("\n=== C2. ¿El perfil del cliente explica nact (y por ende el volumen)? eta² vs nulo, razón max/min (grupos n>=1000) ===")
    d = cst.copy()
    d["dec_income"] = d.groupby("country")["income"].transform(lambda s: pd.qcut(s.rank(method="first"), 10, labels=False))
    d["dec_score"] = pd.qcut(d.credit_score.rank(method="first"), 10, labels=False)
    d["dec_edad"] = (d.edad_d // 3652.5).clip(1, 9)
    d["anio_reg"] = pd.to_datetime("2000-01-01") + pd.to_timedelta(d.reg_d, unit="D")
    d["anio_reg"] = d["anio_reg"].dt.year
    rows = []
    for col in ["segment", "country", "cstatus", "gender", "occupation", "marital_status", "education_level", "detected_accent",
                "mkt", "dec_income", "dec_score", "dec_edad", "anio_reg"]:
        for y in ["nprod", "nact", "ntx"]:
            gg = d.groupby(col, dropna=False)[y].agg(["size", "mean", "var"])
            mu = d[y].mean(); sst = d[y].var(ddof=1) * (len(d) - 1)
            ssb = (gg["size"] * (gg["mean"] - mu) ** 2).sum(); G = len(gg)
            big = gg[gg["size"] >= 1000]
            ssw = ((gg["size"] - 1) * gg["var"].fillna(0)).sum()
            Fst = (ssb / (G - 1)) / (ssw / (len(d) - G))
            rows.append((col, y, G, ssb / sst, (G - 1) / (len(d) - 1), stats.f.sf(Fst, G - 1, len(d) - G),
                         big["mean"].max() / big["mean"].min()))
    res = pd.DataFrame(rows, columns=["atributo", "y", "grupos", "eta2", "eta2_nulo", "p", "razon_max_min"])
    print(res.round(5).to_string(index=False))
    print(f"p<0.05: {(res.p<0.05).sum()} de {len(res)} (esperado ~{0.05*len(res):.1f}); razón max/min máxima={res.razon_max_min.max():.4f}")
    print(d.groupby("segment")[["nprod", "nact", "ntx"]].mean().round(3).to_string())

    print("\n=== C3. GBM held-out (70/30 por cliente): perfil -> nact y perfil -> ntx (SIN nact) ===")
    CAT = ["segment", "country", "cstatus", "gender", "occupation", "marital_status", "education_level", "detected_accent"]
    X = cst[CAT + ["income", "credit_score", "mkt", "reg_d", "edad_d"]].copy()
    for c in CAT:
        X[c] = X[c].astype("category").cat.codes.astype(float)
    perm = rng.permutation(len(X)); ntr = int(0.7 * len(X)); tr, te = perm[:ntr], perm[ntr:]
    for y_col in ["nact", "ntx"]:
        y = cst[y_col].values.astype(float)
        mdl = HistGradientBoostingRegressor(loss="poisson", learning_rate=0.05, max_iter=300, max_leaf_nodes=31, min_samples_leaf=200,
                                            early_stopping=True, validation_fraction=0.15, n_iter_no_change=20,
                                            categorical_features=[c in CAT for c in X.columns], random_state=0)
        mdl.fit(X.iloc[tr], y[tr])
        pm = mdl.predict(X.iloc[te]); pb = np.full(len(te), y[tr].mean())
        r, lo, hi = r2_ci(y[te], pm, pb)
        print(f"{y_col} ~ perfil (13 atributos): R² held-out={r:+.5f} IC95=[{lo:+.5f},{hi:+.5f}]; it={mdl.n_iter_}; rango pred={pm.min():.2f}..{pm.max():.2f}")
    y = cst.ntx.values.astype(float)
    lam = y[tr].sum() / cst.nact.values[tr].sum()
    r, lo, hi = r2_ci(y[te], lam * cst.nact.values[te], np.full(len(te), y[tr].mean()))
    print(f"ntx ~ λ·nact (λ={lam:.4f}): R² held-out={r:.4f} IC95=[{lo:.4f},{hi:.4f}]")
    Xa = X.copy(); Xa["nact"] = cst.nact.values
    mdl = HistGradientBoostingRegressor(loss="poisson", learning_rate=0.05, max_iter=300, max_leaf_nodes=31, min_samples_leaf=200,
                                        early_stopping=True, validation_fraction=0.15, n_iter_no_change=20,
                                        categorical_features=[c in CAT for c in Xa.columns], random_state=0)
    mdl.fit(Xa.iloc[tr], y[tr])
    r, lo, hi = r2_ci(y[te], mdl.predict(Xa.iloc[te]), lam * cst.nact.values[te])
    print(f"ntx ~ perfil + nact (GBM) vs baseline λ·nact: R² relativo={r:+.5f} IC95=[{lo:+.5f},{hi:+.5f}] (<=0 => nada añade)")

if "D" in SECS:
    print("\n=== D. ¿Qué productos quedan Active? P(Active) por atributo (razón max/min, V de Cramér) ===")
    con.execute("""CREATE TEMP TABLE pa AS SELECT pc.*, c.segment, c.country, c.cstatus, year(pc.opened) y_open,
        (pc.expires < DATE '2026-06-17') vencido FROM pc JOIN cu c USING(customer_id)""")
    for col in ["ptype", "currency", "segment", "country", "cstatus", "y_open", "opening_channel", "app", "vencido"]:
        t = Q(f"SELECT {col} g, count(*) k, avg((pstatus='Active')::INT) p FROM pa GROUP BY 1")
        t = t[t.k >= 1000]
        ct = Q(f"SELECT {col} g, pstatus, count(*) k FROM pa GROUP BY 1,2").pivot(index="g", columns="pstatus", values="k").fillna(0)
        chi2, pv, dof, _ = stats.chi2_contingency(ct.values)
        V = np.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))
        print(f"{col:16s} grupos={len(ct):3d} P(Active) {t.p.min():.4f}..{t.p.max():.4f} razón={t.p.max()/t.p.min():.4f}  V={V:.4f} p={pv:.3g}")

if "E" in SECS:
    print("\n=== E1. 'Volumen' en MONTO: USD-eq por producto Active según ptype ===")
    print(Q(f"""SELECT p.ptype, count(DISTINCT p.product_id) nprod, round(count(*)*1.0/count(DISTINCT p.product_id),3) tx_prod,
          round(sum(t.amount/{K_FX.replace('currency','t.currency')})/count(DISTINCT p.product_id),1) usd_por_producto,
          round(avg(t.amount/{K_FX.replace('currency','t.currency')}),1) usd_por_tx
        FROM tx t JOIN pr p USING(product_id) GROUP BY 1 ORDER BY usd_por_producto DESC""").to_string(index=False))
    print(Q(f"""SELECT ttype, count(*) n, round(min(amount/{K_FX}),2) mn, round(avg(amount/{K_FX}),1) media, round(max(amount/{K_FX}),1) mx
        FROM tx GROUP BY 1 ORDER BY media DESC""").to_string(index=False))
    print("\n=== E2. Monto total por cliente (USD-eq): ¿basta nact o importa la mezcla de ptype / el perfil? (held-out 70/30) ===")
    c2 = cst[cst.nact > 0].reset_index(drop=True)
    y = c2.usd.values
    perm = rng.permutation(len(c2)); ntr = int(0.7 * len(c2)); tr, te = perm[:ntr], perm[ntr:]
    base0 = np.full(len(te), y[tr].mean())
    A1 = c2[["nact"]].values
    A2 = c2[["a_ca", "a_cc", "a_tc", "a_td", "a_pp", "a_ph", "a_in", "a_se"]].values
    seg = pd.get_dummies(c2.segment, drop_first=True).values.astype(float)
    A3 = np.hstack([A2, seg, pd.get_dummies(c2.country, drop_first=True).values.astype(float)])
    p1 = LinearRegression().fit(A1[tr], y[tr]).predict(A1[te])
    p2 = LinearRegression().fit(A2[tr], y[tr]).predict(A2[te])
    p3 = LinearRegression().fit(A3[tr], y[tr]).predict(A3[te])
    for lab, pr_, bb in [("usd ~ nact", p1, base0), ("usd ~ #activos por ptype", p2, base0), ("usd ~ ptype + segmento + país", p3, base0),
                         ("#activos por ptype vs nact (R² relativo)", p2, p1), ("+segmento+país vs ptype (R² relativo)", p3, p2)]:
        r, lo, hi = r2_ci(y[te], pr_, bb)
        print(f"{lab:42s} R²={r:+.4f} IC95=[{lo:+.4f},{hi:+.4f}]")
    print("coef. USD por producto activo de cada ptype:",
          dict(zip(["CA", "CC", "TC", "TD", "PP", "PH", "IN", "SE"], LinearRegression().fit(A2, y).coef_.round(0))))
    print("USD-eq medio por cliente según segmento (clientes con activos):")
    print(c2.groupby("segment").agg(n=("usd", "size"), usd=("usd", "mean"), nact=("nact", "mean"), usd_por_act=("usd", lambda s: s.sum())).assign(
        usd_por_act=lambda t: t.usd_por_act / (t.nact * t.n)).round(1).to_string())

if "F" in SECS:
    print("\n=== F. Productos Active con 0 tx ===")
    print(Q("""SELECT pc.product_id, pc.ptype, pc.currency, pc.opened, pc.expires, c.segment, c.country, c.cstatus
        FROM pc JOIN cu c USING(customer_id) WHERE pc.pstatus='Active' AND pc.n=0""").to_string(index=False))

if "G" in SECS:
    print("\n=== G. Utilidad para el flujo de tarjetas ===")
    print(Q("""SELECT p.ptype, p.pstatus, count(*) nprod, sum(coalesce(t.n,0)) ntx FROM pr p
        LEFT JOIN (SELECT product_id, count(*) n FROM tx GROUP BY 1) t USING(product_id)
        WHERE p.ptype IN ('Tarjeta Crédito','Tarjeta Débito') GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False))
    print(Q("""SELECT p.ptype, count(*) tarjetas_activas,
          round(avg(coalesce(t.npur,0)),3) compras_por_tarjeta_3a,
          round(avg((coalesce(t.p30,0)>0)::INT),4) p_compra_ult_30d,
          round(avg((coalesce(t.p90,0)>0)::INT),4) p_compra_ult_90d,
          round(avg((coalesce(t.d30,0)>0)::INT),4) p_rechazo_ult_30d
        FROM pr p LEFT JOIN (SELECT product_id, count(*) FILTER (WHERE ttype='Purchase') npur,
             count(*) FILTER (WHERE ttype='Purchase' AND process_date >= DATE '2026-05-18') p30,
             count(*) FILTER (WHERE ttype='Purchase' AND process_date >= DATE '2026-03-19') p90,
             count(*) FILTER (WHERE status='Declined' AND process_date >= DATE '2026-05-18') d30
           FROM tx GROUP BY 1) t USING(product_id)
        WHERE p.pstatus='Active' AND p.ptype IN ('Tarjeta Crédito','Tarjeta Débito') GROUP BY 1""").to_string(index=False))

if "H" in SECS:
    print("\n=== H. Nivel cliente: ntx por nact, Gini observado vs simulado Poisson(λ·nact) ===")
    c = Q("""SELECT coalesce(p.nact,0) nact, coalesce(t.n,0) ntx FROM cu LEFT JOIN
        (SELECT customer_id, count(*) FILTER (WHERE pstatus='Active') nact FROM pr GROUP BY 1) p USING(customer_id)
        LEFT JOIN (SELECT customer_id, count(*) n FROM tx GROUP BY 1) t USING(customer_id)""")
    t = c.groupby("nact").ntx.agg(["size", "mean", "std"]).round(2)
    t["sd_poisson"] = np.sqrt(13.0161 * t.index.values).round(2)
    print(t.T.to_string())
    print(f"clientes sin activos={int((c.nact==0).sum()):,} ({(c.nact==0).mean():.2%}); de ellos con tx={int(((c.nact==0)&(c.ntx>0)).sum())}")

    def gini(x):
        x = np.sort(np.asarray(x, float)); n = len(x)
        return 2 * np.sum(np.arange(1, n + 1) * x) / (n * x.sum()) - (n + 1) / n

    top10 = lambda x: np.sort(x)[-len(x) // 10:].sum() / x.sum()
    lam = c.ntx.sum() / c.nact.sum()
    sims = [rng.poisson(lam * c.nact.values) for _ in range(20)]
    r = np.corrcoef(c.ntx, c.nact)[0, 1]
    ceil = (lam ** 2 * c.nact.var()) / (lam ** 2 * c.nact.var() + lam * c.nact.mean())
    print(f"Gini obs={gini(c.ntx):.4f} sim={np.mean([gini(s) for s in sims]):.4f}; top10% obs={top10(c.ntx.values):.4f} "
          f"sim={np.mean([top10(s) for s in sims]):.4f}; corr={r:.4f} R²={r*r:.4f} techo Poisson={ceil:.4f}")

if "I" in SECS:
    print("\n=== I. Reparto dentro del cliente: corr entre conteos de 2 productos Active del mismo cliente (nact=2..4) ===")
    for k in [2, 3, 4]:
        d = Q(f"""WITH a AS (SELECT customer_id, n, row_number() OVER (PARTITION BY customer_id ORDER BY product_id) rn
                  FROM pc WHERE pstatus='Active' AND customer_id IN
                  (SELECT customer_id FROM pc WHERE pstatus='Active' GROUP BY 1 HAVING count(*)={k}))
                SELECT a1.n n1, a2.n n2 FROM a a1 JOIN a a2 ON a1.customer_id=a2.customer_id AND a1.rn=1 AND a2.rn=2""")
        r = np.corrcoef(d.n1, d.n2)[0, 1]
        bs = [np.corrcoef(*d.sample(frac=1, replace=True, random_state=i)[["n1", "n2"]].values.T)[0, 1] for i in range(300)]
        print(f"nact={k}: clientes={len(d):,} corr={r:+.4f} IC95=[{np.percentile(bs,2.5):+.4f},{np.percentile(bs,97.5):+.4f}] "
              f"(0 => Poisson independiente; <0 => total fijo repartido; >0 => propensión del cliente)")
