"""Verificación independiente (repro, reintento): 'El volumen transaccional es 13 tx por producto activo (Poisson)
y nada más lo explica'.

Secciones
  A. Integridad del vínculo tx -> pr -> cu (huérfanos, dueño, estado del producto).
  B. Conteo por producto: por pstatus; distribución en Active (media, varianza, dispersión, ceros, GOF Poisson).
  C. Media por ptype y por año de apertura + exposición temporal (tx previas a la apertura).
  D. Nivel cliente: ntx vs #productos activos, R2 y techo teórico, clientes sin activos, Gini y top-10%.
  E. '¿Nada más lo explica?': ANOVA/eta2 por ~25 atributos (producto y cliente) vs nulo, correlación split-half
     (heterogeneidad latente) y modelo GBM Poisson held-out agrupado por cliente (D2 con IC95 bootstrap).
Ejecutar: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_behavior_volumen_13_por_producto_repro.py
"""
import duckdb
import numpy as np
import pandas as pd
from scipy import stats

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 80)

con = duckdb.connect("data/analysis.duckdb", read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()
F = lambda s: con.execute(s).fetchall()
TMID = "2024-12-17 06:00:00"  # mitad de la ventana de ts (2023-06-17 06:00 -> 2026-06-18 06:00, 1096 días)

print("=== A. Integridad tx -> pr -> cu ===")
print(Q("""SELECT count(*) ntx, count(DISTINCT transaction_id) ids_unicos, count(t.product_id) con_pid,
      count(*) FILTER (WHERE p.product_id IS NULL) huerfanas,
      count(*) FILTER (WHERE p.customer_id <> t.customer_id) dueno_distinto,
      count(*) FILTER (WHERE p.pstatus <> 'Active') en_no_active,
      count(DISTINCT t.product_id) productos_con_tx
    FROM tx t LEFT JOIN pr p USING(product_id)""").to_string(index=False))

con.execute(f"""CREATE TEMP TABLE cnt AS SELECT t.product_id, count(*) n,
     count(*) FILTER (WHERE t.ts <  TIMESTAMP '{TMID}') h1,
     count(*) FILTER (WHERE t.ts >= TIMESTAMP '{TMID}') h2,
     count(*) FILTER (WHERE t.ts::DATE < p.opened) pre,
     count(*) FILTER (WHERE t.status='Declined') ndec
   FROM tx t JOIN pr p USING(product_id) GROUP BY 1""")
con.execute("""CREATE TEMP TABLE pp AS SELECT p.product_id, p.customer_id, p.ptype, p.currency, p.opening_channel, p.app,
     p.opened, p.expires, p.bal, p.credit_limit, p.rate, p.dpd, p.pstatus, p.opening_branch_id,
     coalesce(c.n,0) n, coalesce(c.h1,0) h1, coalesce(c.h2,0) h2, coalesce(c.pre,0) pre, coalesce(c.ndec,0) ndec
   FROM pr p LEFT JOIN cnt c USING(product_id)""")

print("\n=== B. Conteo por producto ===")
print(Q("""SELECT pstatus, count(*) nprod, sum(n) ntx, count(*) FILTER (WHERE n>0) con_tx, round(avg(n),4) media
           FROM pp GROUP BY 1 ORDER BY 1""").to_string(index=False))
N, m, v, mn, mx, z0 = F("SELECT count(*), avg(n), var_samp(n), min(n), max(n), count(*) FILTER (WHERE n=0) FROM pp WHERE pstatus='Active'")[0]
ntx_tot = F("SELECT count(*) FROM tx")[0][0]
se_disp = np.sqrt(2.0 / (N - 1))
print(f"tx totales / productos Active = {ntx_tot:,} / {N:,} = {ntx_tot/N:.4f}")
print(f"Active: media={m:.4f} (IC95 {m-1.96*np.sqrt(m/N):.4f}-{m+1.96*np.sqrt(m/N):.4f}) var={v:.4f} "
      f"dispersión={v/m:.4f} (SE bajo Poisson={se_disp:.4f}, z={(v/m-1)/se_disp:+.2f}) min={mn} max={mx}")
print(f"Active con 0 tx: {z0} (esperado Poisson: {N*np.exp(-m):.2f}; P(>= {z0})={stats.poisson.sf(z0-1, N*np.exp(-m)):.3f})")
h = Q("SELECT n, count(*) c FROM pp WHERE pstatus='Active' GROUP BY 1").set_index("n")["c"]
obs = h.reindex(range(0, int(mx) + 1), fill_value=0).values.astype(float)
pmf = stats.poisson.pmf(np.arange(int(mx) + 1), m)
exp = pmf * N
exp[-1] += N * stats.poisson.sf(int(mx), m)
ob, eb, ao, ae = [], [], 0.0, 0.0
for o, e in zip(obs, exp):
    ao += o; ae += e
    if ae >= 10:
        ob.append(ao); eb.append(ae); ao = ae = 0.0
ob[-1] += ao; eb[-1] += ae
ob, eb = np.array(ob), np.array(eb)
chi2 = ((ob - eb) ** 2 / eb).sum(); dfree = len(ob) - 2
print(f"GOF Poisson(λ̂): chi2={chi2:.1f} df={dfree} p={stats.chi2.sf(chi2, dfree):.3f}; "
      f"variación total={0.5*np.abs(obs/N - pmf).sum():.5f}; cuantiles obs p1/p50/p99 = "
      f"{F('SELECT quantile_disc(n,0.01), quantile_disc(n,0.5), quantile_disc(n,0.99) FROM pp WHERE pstatus=' + chr(39) + 'Active' + chr(39))[0]}"
      f" vs Poisson {stats.poisson.ppf([0.01, 0.5, 0.99], m)}")

print("\n=== C. Por ptype y por año de apertura (solo Active) ===")
for expr, lab in [("ptype", "ptype"), ("year(opened)", "año apertura")]:
    d = Q(f"""SELECT {expr} g, count(*) k, avg(n) media, var_samp(n) var FROM pp WHERE pstatus='Active' GROUP BY 1 ORDER BY 1""")
    d["disp"] = d["var"] / d["media"]
    d["z_vs_global"] = (d["media"] - m) / np.sqrt(m / d["k"])
    print(f"[{lab}] rango medias = {d.media.min():.3f} .. {d.media.max():.3f}")
    print(d.round(4).to_string(index=False))
print("\n--- Exposición: tx fechadas antes de la apertura del producto ---")
print(Q("""SELECT CASE WHEN opened < DATE '2023-06-17' THEN 'a) abierto antes de la ventana'
                       WHEN opened < DATE '2026-01-01' THEN 'b) abierto 2023-06-17..2025'
                       ELSE 'c) abierto en 2026' END grupo,
             count(*) nprod, round(avg(n),3) tx_media, sum(pre) tx_antes_apertura, round(sum(pre)/sum(n),4) frac_antes,
             round(avg(greatest(0, date_diff('day', DATE '2023-06-17', opened)))/1096.0, 4) frac_esperada_si_uniforme
           FROM pp WHERE pstatus='Active' GROUP BY 1 ORDER BY 1""").to_string(index=False))
print("fracción global de tx con fecha < apertura del producto:", round(F("SELECT sum(pre)/sum(n) FROM pp")[0][0], 4))
print("corr(n, días de exposición en ventana) Active:",
      round(F("""SELECT corr(n, date_diff('day', greatest(opened, DATE '2023-06-17'), DATE '2026-06-17')) FROM pp WHERE pstatus='Active'""")[0][0], 5))

print("\n=== D. Nivel cliente ===")
con.execute("""CREATE TEMP TABLE cst AS SELECT c.customer_id, coalesce(t.ntx,0) ntx, coalesce(p.nprod,0) nprod, coalesce(p.nact,0) nact,
     coalesce(p.ntx_prod,0) ntx_prod, coalesce(t.h1,0) h1, coalesce(t.h2,0) h2
   FROM cu c
   LEFT JOIN (SELECT customer_id, count(*) ntx, count(*) FILTER (WHERE ts < TIMESTAMP '""" + TMID + """') h1,
                     count(*) FILTER (WHERE ts >= TIMESTAMP '""" + TMID + """') h2 FROM tx GROUP BY 1) t USING(customer_id)
   LEFT JOIN (SELECT customer_id, count(*) nprod, count(*) FILTER (WHERE pstatus='Active') nact, sum(n) ntx_prod FROM pp GROUP BY 1) p USING(customer_id)""")
print("clientes en tx que no están en cu:", F("SELECT count(DISTINCT customer_id) FROM tx ANTI JOIN cu USING(customer_id)")[0][0],
      "| clientes con ntx(tx.customer_id) != suma por sus productos:", F("SELECT count(*) FROM cst WHERE ntx <> ntx_prod")[0][0])
d = Q("SELECT customer_id, ntx, nprod, nact, h1, h2 FROM cst")
tab = d.groupby("nact").agg(ncli=("ntx", "size"), media=("ntx", "mean"), sd=("ntx", "std"), con_tx=("ntx", lambda s: int((s > 0).sum())))
tab["tx_por_act"] = tab["media"] / tab.index.to_series().replace(0, np.nan)
tab["sd_poisson"] = np.sqrt(m * tab.index.values)
print(tab.round(3).to_string())
n0 = (d.nact == 0).sum()
print(f"clientes={len(d):,}; sin productos activos={n0:,} ({n0/len(d):.2%}), de ellos con tx>0={int((d[d.nact==0].ntx>0).sum())}; "
      f"sin ningún producto={int((d.nprod==0).sum()):,}")
r = np.corrcoef(d.ntx, d.nact)[0, 1]
r2_teo = (m ** 2 * d.nact.var()) / (m ** 2 * d.nact.var() + m * d.nact.mean())
print(f"corr(ntx,nact)={r:.4f} R2={r**2:.4f}; techo teórico si ntx~Poisson(λ·nact) = {r2_teo:.4f}")
act = d[d.nact > 0]
lam_c = act.ntx.sum() / act.nact.sum()
zres = (act.ntx - lam_c * act.nact) / np.sqrt(lam_c * act.nact)
print(f"residuo z=(ntx-λ·nact)/sqrt(λ·nact) en clientes con activos: media={zres.mean():+.4f} var={zres.var():.4f} (Poisson=1) "
      f"max={zres.max():.2f} min={zres.min():.2f} (max|z| esperado ~{stats.norm.isf(0.25/len(zres)):.2f}); #|z|>5={(np.abs(zres)>5).sum()}")


def gini(x):
    x = np.sort(np.asarray(x, dtype=float)); n = len(x); s = x.sum()
    return (2 * np.sum(np.arange(1, n + 1) * x) / (n * s)) - (n + 1) / n


def top_share(x, q=0.10):
    x = np.sort(np.asarray(x, dtype=float)); k = int(round(len(x) * q))
    return x[-k:].sum() / x.sum()


rng = np.random.default_rng(42)
sims = [rng.poisson(m * d.nact.values) for _ in range(20)]
print(f"Gini ntx (150k clientes)={gini(d.ntx):.4f} top10%={top_share(d.ntx):.4f} top1%={top_share(d.ntx, 0.01):.4f}")
print(f"Gini esperado por nact solo (λ·nact)={gini(m*d.nact):.4f} top10%={top_share(m*d.nact):.4f};  "
      f"Gini simulado Poisson(λ·nact) media 20 sims={np.mean([gini(s) for s in sims]):.4f} top10%={np.mean([top_share(s) for s in sims]):.4f}")
print(f"Gini sólo clientes con nact>0: obs={gini(act.ntx):.4f} vs sim={np.mean([gini(s[d.nact.values>0]) for s in sims]):.4f}")

print("\n=== E1. ¿Otro atributo explica el conteo por producto? (Active; ANOVA, eta2 vs nulo) ===")
con.execute("""CREATE TEMP TABLE pa AS SELECT pp.*, c.segment, c.country, c.cstatus, c.gender, c.mkt, c.income, c.credit_score,
     c.registration_date, c.dob, c.occupation, c.marital_status, c.education_level, c.detected_accent, c.city ccity, s.nact
   FROM pp JOIN cu c USING(customer_id) JOIN cst s USING(customer_id) WHERE pp.pstatus='Active'""")
SST = F("SELECT var_samp(n)*(count(*)-1) FROM pa")[0][0]
dec = lambda x, part="": f"CASE WHEN {x} IS NULL THEN 0 ELSE ntile(10) OVER (PARTITION BY ({x} IS NULL){part} ORDER BY {x}) END"
attrs = [("ptype", "ptype"), ("year(opened)", "año apertura"), ("strftime(opened,'%Y-%m')", "mes apertura"), ("currency", "moneda"),
         ("opening_channel", "canal apertura"), ("app", "app"), ("(dpd>0)", "dpd>0"), (dec("bal"), "decil saldo"),
         (dec("credit_limit"), "decil límite"), (dec("rate"), "decil tasa"), ("year(expires)", "año vencimiento"),
         ("opening_branch_id", "sucursal apertura"), ("segment", "segmento"), ("country", "país"), ("cstatus", "cstatus"),
         ("gender", "género"), ("mkt", "mkt"), (dec("income", ", country"), "decil ingreso (por país)"),
         (dec("credit_score"), "decil credit_score"), ("year(registration_date)", "año registro"),
         ("(date_diff('year', dob, DATE '2026-06-17')//10)*10", "década edad"), ("occupation", "ocupación"),
         ("marital_status", "estado civil"), ("education_level", "educación"), ("detected_accent", "acento"),
         ("ccity", "ciudad cliente"), ("least(nact, 8)", "#activos del cliente")]
rows = []
for expr, lab in attrs:
    g = Q(f"SELECT g, count(*) k, avg(n) media, var_samp(n) var FROM (SELECT {expr} g, n FROM pa) GROUP BY 1")
    G = len(g)
    ssb = (g.k * (g.media - m) ** 2).sum()
    ssw = ((g.k - 1) * g["var"].fillna(0)).sum()
    Fst = (ssb / (G - 1)) / (ssw / (N - G)) if G > 1 else np.nan
    big = g[g.k >= 1000]
    rows.append((lab, G, ssb / SST, (G - 1) / (N - 1), stats.f.sf(Fst, G - 1, N - G) if G > 1 else np.nan,
                 big.media.min(), big.media.max(), big.media.max() / big.media.min()))
res = pd.DataFrame(rows, columns=["atributo", "grupos", "eta2", "eta2_nulo", "p_ANOVA", "media_min(k>=1000)", "media_max(k>=1000)", "razón_max/min"])
print(res.round(6).to_string(index=False))
print(f"atributos con p<0.05: {int((res.p_ANOVA<0.05).sum())} de {len(res)} (esperado por azar ~{0.05*len(res):.1f}); "
      f"eta2 máximo={res.eta2.max():.6f}; razón max/min máxima={res['razón_max/min'].max():.4f}")

print("\n=== E2. Heterogeneidad latente: correlación split-half (misma unidad, periodos disjuntos) ===")
agg = Q("""SELECT customer_id, count(*) k, sum(h1) a, sum(h2) b, sum(h1*h1) aa, sum(h2*h2) bb, sum(h1*h2) ab FROM pa GROUP BY 1""")
A = agg[["k", "a", "b", "aa", "bb", "ab"]].values.astype(float)


def corr_s(S):
    k, a, b, aa, bb, ab = S
    return (ab / k - a / k * b / k) / np.sqrt((aa / k - (a / k) ** 2) * (bb / k - (b / k) ** 2))


r_p = corr_s(A.sum(0))
bs = np.array([corr_s(A[rng.integers(0, len(A), len(A))].sum(0)) for _ in range(300)])
print(f"producto: corr(tx H1, tx H2)={r_p:+.4f} IC95 bootstrap por cliente=[{np.percentile(bs,2.5):+.4f},{np.percentile(bs,97.5):+.4f}] "
      f"(Poisson homogéneo => 0; propensión latente => >0; total fijo => <0)")
l1 = act.h1.sum() / act.nact.sum(); l2 = act.h2.sum() / act.nact.sum()
r1 = ((act.h1 - l1 * act.nact) / np.sqrt(l1 * act.nact)).values
r2 = ((act.h2 - l2 * act.nact) / np.sqrt(l2 * act.nact)).values
rc = np.corrcoef(r1, r2)[0, 1]
bs = []
for _ in range(300):
    ix = rng.integers(0, len(r1), len(r1)); bs.append(np.corrcoef(r1[ix], r2[ix])[0, 1])
print(f"cliente: corr(residuo H1, residuo H2) dado nact={rc:+.4f} IC95=[{np.percentile(bs,2.5):+.4f},{np.percentile(bs,97.5):+.4f}]")

print("\n=== E3. Modelo multivariable held-out (GBM Poisson, split agrupado por cliente) ===")
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupShuffleSplit

con.execute("""CREATE TEMP TABLE oc AS SELECT c.customer_id, coalesce(a.n,0) n_cc, coalesce(b.n,0) n_cp FROM cu c
   LEFT JOIN (SELECT customer_id, count(*) n FROM cc GROUP BY 1) a USING(customer_id)
   LEFT JOIN (SELECT customer_id, count(*) n FROM cp GROUP BY 1) b USING(customer_id)""")
X = Q("""SELECT pa.customer_id, pa.n, pa.ptype, pa.currency, pa.opening_channel, pa.app::INT app,
       date_diff('day', DATE '2018-01-01', pa.opened) opened_d, date_diff('day', DATE '2018-01-01', pa.expires) expires_d,
       pa.bal, pa.credit_limit, pa.rate, pa.dpd, pa.segment, pa.country, pa.cstatus, pa.gender, pa.mkt::INT mkt,
       pa.income, pa.credit_score, date_diff('day', DATE '2010-01-01', pa.registration_date::DATE) reg_d,
       date_diff('day', pa.dob, DATE '2026-06-17') edad_d, pa.nact, oc.n_cc, oc.n_cp
     FROM pa JOIN oc USING(customer_id) WHERE hash(pa.customer_id) % 2 = 0""")
y = X.pop("n").values.astype(float); grp = X.pop("customer_id").values
CAT = ["ptype", "currency", "opening_channel", "segment", "country", "cstatus", "gender"]
for c in CAT:
    X[c] = X[c].astype("category").cat.codes.astype(float)
tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=0).split(X, y, grp))
mdl = HistGradientBoostingRegressor(loss="poisson", learning_rate=0.05, max_iter=400, max_leaf_nodes=31, min_samples_leaf=300,
                                    early_stopping=True, validation_fraction=0.15, n_iter_no_change=20,
                                    categorical_features=[c in CAT for c in X.columns], random_state=0)
mdl.fit(X.iloc[tr], y[tr])
pm = mdl.predict(X.iloc[te]); pb = np.full(len(te), y[tr].mean()); yt = y[te]


def pdev(yv, mu):
    mu = np.clip(mu, 1e-9, None)
    return 2 * (np.where(yv > 0, yv * np.log(np.where(yv > 0, yv, 1) / mu), 0.0) - (yv - mu))


gd = pd.DataFrame({"g": grp[te], "dm": pdev(yt, pm), "db": pdev(yt, pb), "sm": (yt - pm) ** 2, "sb": (yt - pb) ** 2}).groupby("g").sum().values
met = lambda a: (1 - a[:, 0].sum() / a[:, 1].sum(), 1 - a[:, 2].sum() / a[:, 3].sum())
d2, r2m = met(gd)
bsm = np.array([met(gd[rng.integers(0, len(gd), len(gd))]) for _ in range(500)])
print(f"n_train={len(tr):,} n_test={len(te):,} iteraciones={mdl.n_iter_}; D2 Poisson vs media constante={d2:+.5f} "
      f"IC95=[{np.percentile(bsm[:,0],2.5):+.5f},{np.percentile(bsm[:,0],97.5):+.5f}]; R2 vs media={r2m:+.5f} "
      f"IC95=[{np.percentile(bsm[:,1],2.5):+.5f},{np.percentile(bsm[:,1],97.5):+.5f}]; rango predicciones={pm.min():.2f}..{pm.max():.2f}")

print("\n=== F. Refinamientos: ¿'heavy users'? y ¿Poisson o Binomial por día? ===")
nz = d.nact.values > 0
zsim_max = []
for s in sims:
    zs = (s[nz] - m * d.nact.values[nz]) / np.sqrt(m * d.nact.values[nz])
    zsim_max.append(zs.max())
print(f"max z observado={zres.max():.2f}; max z en 20 simulaciones Poisson(λ·nact): mediana={np.median(zsim_max):.2f} "
      f"rango={min(zsim_max):.2f}..{max(zsim_max):.2f} (la cola Poisson es más pesada que la normal)")
o = act.assign(z=zres).sort_values("z", ascending=False).head(3)
for _, rr in o.iterrows():
    pv = stats.poisson.sf(rr.ntx - 1, lam_c * rr.nact)
    print(f"   nact={int(rr.nact)} ntx={int(rr.ntx)} z={rr.z:.2f} P(X>=ntx)={pv:.2e} Bonferroni(x{len(act):,})={min(1, pv*len(act)):.3f}")
# colisiones mismo día por producto: Poisson/uniforme => E[pares] = sum C(n,2)/1096 ; 'máx 1 tx por día' => 0
pairs_obs = F("SELECT sum(c*(c-1)/2) FROM (SELECT product_id, ts::DATE dd, count(*) c FROM tx GROUP BY 1,2)")[0][0]
pairs_exp = F("SELECT sum(n*(n-1)/2)/1096.0 FROM pp WHERE pstatus='Active'")[0][0]
print(f"pares de tx del mismo producto el mismo día: observados={pairs_obs:,.0f} esperados si ts uniforme={pairs_exp:,.0f} "
      f"(razón {pairs_obs/pairs_exp:.3f})")
print(f"dispersión esperada si Binomial(1096 días, λ/1096)={1-m/1096:.4f}; observada={v/m:.4f}; Poisson=1")
print(Q("""SELECT least(nact,6) nact_cli, count(*) k, round(avg(n),3) media, round(var_samp(n)/avg(n),4) disp FROM pa GROUP BY 1 ORDER BY 1""").to_string(index=False))
