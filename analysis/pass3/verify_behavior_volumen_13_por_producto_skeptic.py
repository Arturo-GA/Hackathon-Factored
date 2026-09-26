"""Verificador escéptico: 'El volumen transaccional es 13 tx por producto activo (Poisson) y nada más lo explica'.

Intentos de refutación:
 A. Procedencia/doble conteo: IDs únicos, huérfanos, dueño tx vs dueño producto, tx en no-Active.
 B. ¿Poisson o algo distinto? (dispersión, GOF, ceros, máximo, λ vs 13).
 C. Heterogeneidad LATENTE (no observada): correlación split-half del conteo del mismo producto en dos
    periodos disjuntos (H1/H2 y meses pares/impares). Poisson homogéneo => corr≈0; propensión oculta => corr>0;
    total fijo por producto => corr<0. Lo mismo a nivel cliente con residuos estandarizados.
 D. Orden de generación: conteo vs posición del producto/cliente en el archivo fuente.
 E. 'Heavy users': residuos z extremos a nivel cliente.
 F. Utilidad: densidad temporal (tx/mes por producto, % productos/clientes con tx en últimos 30/90/365 días),
    tx previas a la apertura del producto.
"""
import duckdb
import numpy as np
import pandas as pd
from scipy import stats

pd.set_option("display.width", 200)
con = duckdb.connect("data/analysis.duckdb", read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
Q = lambda s: con.execute(s).df()
F = lambda s: con.execute(s).fetchall()

print("=== A. Procedencia ===")
print(Q("""SELECT count(*) ntx, count(DISTINCT transaction_id) ids, count(product_id) con_pid,
   sum((p.product_id IS NULL)::INT) huerfanas, sum((p.customer_id <> t.customer_id)::INT) dueno_distinto,
   sum((p.pstatus <> 'Active')::INT) en_no_active FROM tx t LEFT JOIN pr p USING(product_id)""").to_string(index=False))

T0, T1 = "2023-06-17 06:00:00", "2026-06-18 06:00:00"   # ventana real de ts (desfase +6h)
TM = "2024-12-17 06:00:00"                                # mitad (548.5 días)
con.execute(f"""CREATE TEMP TABLE pn AS
  SELECT p.product_id, p.customer_id, p.ptype, p.pstatus, p.opened,
         coalesce(t.n,0) n, coalesce(t.h1,0) h1, coalesce(t.h2,0) h2, coalesce(t.mo,0) mo, coalesce(t.me,0) me,
         coalesce(t.d30,0) d30, coalesce(t.d90,0) d90, coalesce(t.d365,0) d365, coalesce(t.ndec,0) ndec,
         coalesce(t.dh1,0) dh1, coalesce(t.dh2,0) dh2, coalesce(t.pre,0) pre
  FROM pr p LEFT JOIN (
    SELECT t.product_id, count(*) n,
      sum((ts <  TIMESTAMP '{TM}')::INT) h1, sum((ts >= TIMESTAMP '{TM}')::INT) h2,
      sum((month(ts) % 2 = 1)::INT) mo, sum((month(ts) % 2 = 0)::INT) me,
      sum((ts >= TIMESTAMP '{T1}' - INTERVAL 30 DAY)::INT) d30, sum((ts >= TIMESTAMP '{T1}' - INTERVAL 90 DAY)::INT) d90,
      sum((ts >= TIMESTAMP '{T1}' - INTERVAL 365 DAY)::INT) d365,
      sum((status='Declined')::INT) ndec,
      sum((status='Declined' AND ts < TIMESTAMP '{TM}')::INT) dh1, sum((status='Declined' AND ts >= TIMESTAMP '{TM}')::INT) dh2,
      sum((ts::DATE < p2.opened)::INT) pre
    FROM tx t JOIN pr p2 USING(product_id) GROUP BY 1) t USING(product_id)""")

print("\n=== B. Distribución por producto Active ===")
N, m, v, mx, z0 = F("SELECT count(*), avg(n), var_samp(n), max(n), sum((n=0)::INT) FROM pn WHERE pstatus='Active'")[0]
se_l = np.sqrt(m / N)
print(f"N={N:,} λ̂={m:.4f} IC95=[{m-1.96*se_l:.4f},{m+1.96*se_l:.4f}] (z vs 13.000 = {(m-13)/se_l:.2f})  var={v:.4f} disp={v/m:.4f} "
      f"(SE nulo {np.sqrt(2/(N-1)):.4f}, z={(v/m-1)/np.sqrt(2/(N-1)):.2f})")
print(f"ceros: {z0} (esperado {N*np.exp(-m):.2f});  máx={mx}  P(max>={mx}) bajo Poisson = {1-(1-stats.poisson.sf(mx-1, m))**N:.3f}")
h = Q("SELECT n, count(*) c FROM pn WHERE pstatus='Active' GROUP BY 1 ORDER BY 1").set_index("n")["c"]
obs = h.reindex(range(0, mx + 1), fill_value=0).values.astype(float)
pmf = stats.poisson.pmf(np.arange(mx + 1), m); exp = pmf * N; exp[-1] += N * stats.poisson.sf(mx, m)
ob, eb, ao, ae = [], [], 0, 0
for o, e in zip(obs, exp):
    ao += o; ae += e
    if ae >= 10:
        ob.append(ao); eb.append(ae); ao = ae = 0
ob[-1] += ao; eb[-1] += ae
ob, eb = np.array(ob), np.array(eb)
chi2 = ((ob - eb) ** 2 / eb).sum(); df_ = len(ob) - 2
print(f"GOF Poisson: chi2={chi2:.1f} df={df_} p={stats.chi2.sf(chi2, df_):.3f}; variación total={0.5*np.abs(obs/N-pmf).sum():.5f}")
# alternativas: NB (sobre-dispersión) / Binomial fija (sub-dispersión) -> dispersión ~1 las descarta
print("por ptype:", Q("SELECT ptype, count(*) k, round(avg(n),3) m, round(var_samp(n)/avg(n),3) disp FROM pn WHERE pstatus='Active' GROUP BY 1 ORDER BY 2 DESC").to_dict("records"))

print("\n=== C. Heterogeneidad latente: split-half por producto (misma unidad, periodos disjuntos) ===")
# agregados por cliente para bootstrap agrupado por cliente
agg = Q("""SELECT customer_id, count(*) k,
   sum(h1) a1, sum(h2) a2, sum(h1*h1) a11, sum(h2*h2) a22, sum(h1*h2) a12,
   sum(mo) b1, sum(me) b2, sum(mo*mo) b11, sum(me*me) b22, sum(mo*me) b12,
   sum(dh1) c1, sum(dh2) c2, sum(dh1*dh1) c11, sum(dh2*dh2) c22, sum(dh1*dh2) c12
   FROM pn WHERE pstatus='Active' GROUP BY 1""")
A = agg.drop(columns="customer_id").values.astype(float)


def corr_from(S, i):
    k = S[0]; s1, s2, s11, s22, s12 = S[i:i + 5]
    c = s12 / k - (s1 / k) * (s2 / k)
    return c / np.sqrt((s11 / k - (s1 / k) ** 2) * (s22 / k - (s2 / k) ** 2))


rng = np.random.default_rng(7)
B = 400
idxs = [rng.integers(0, len(A), len(A)) for _ in range(B)]
for lab, i in [("H1 vs H2 (tx)", 1), ("meses impares vs pares (tx)", 6), ("H1 vs H2 (rechazos Declined)", 11)]:
    r = corr_from(A.sum(0), i)
    bs = np.array([corr_from(A[ix].sum(0), i) for ix in idxs])
    print(f"{lab}: corr={r:+.4f} IC95 bootstrap por cliente=[{np.percentile(bs,2.5):+.4f},{np.percentile(bs,97.5):+.4f}]  "
          f"(R² máx de un 'predictor de propensión' = {max(r,0)**2:.5f})")
# rechazos por producto: dispersión (¿productos 'problemáticos'?)
md, vd = F("SELECT avg(ndec), var_samp(ndec) FROM pn WHERE pstatus='Active'")[0]
print(f"Declined por producto: media={md:.4f} var={vd:.4f} disp={vd/md:.4f}; % productos Active con >=1 Declined = "
      f"{F('SELECT avg((ndec>0)::INT) FROM pn WHERE pstatus=' + chr(39) + 'Active' + chr(39))[0][0]:.4f} (Poisson esperado {1-np.exp(-md):.4f})")

print("\n--- nivel cliente: residuos estandarizados H1 vs H2 (propensión del cliente más allá de nact) ---")
cst = Q(f"""SELECT c.customer_id, coalesce(a.nact,0) nact, coalesce(a.nprod,0) nprod, coalesce(t.n,0) n, coalesce(t.h1,0) h1, coalesce(t.h2,0) h2
  FROM cu c LEFT JOIN (SELECT customer_id, count(*) nprod, sum((pstatus='Active')::INT) nact FROM pr GROUP BY 1) a USING(customer_id)
  LEFT JOIN (SELECT customer_id, count(*) n, sum((ts < TIMESTAMP '{TM}')::INT) h1, sum((ts >= TIMESTAMP '{TM}')::INT) h2 FROM tx GROUP BY 1) t USING(customer_id)""")
act = cst[cst.nact > 0]
l1 = act.h1.sum() / act.nact.sum(); l2 = act.h2.sum() / act.nact.sum()
r1 = (act.h1 - l1 * act.nact) / np.sqrt(l1 * act.nact); r2 = (act.h2 - l2 * act.nact) / np.sqrt(l2 * act.nact)
rc = np.corrcoef(r1, r2)[0, 1]
bs = []
R1, R2 = r1.values, r2.values
for _ in range(400):
    ix = rng.integers(0, len(R1), len(R1)); bs.append(np.corrcoef(R1[ix], R2[ix])[0, 1])
print(f"clientes nact>0: {len(act):,}; λ_H1={l1:.3f} λ_H2={l2:.3f}; corr residuos H1/H2={rc:+.4f} IC95=[{np.percentile(bs,2.5):+.4f},{np.percentile(bs,97.5):+.4f}]")
z = (act.n - m * act.nact) / np.sqrt(m * act.nact)
print(f"E. residuo z del total: media={z.mean():+.4f} var={z.var():.4f} (Poisson=1)  max|z|={np.abs(z).max():.2f} "
      f"(esperado max|z| normal con n={len(z):,}: ~{stats.norm.isf(0.25/len(z)):.2f});  #|z|>5 = {(np.abs(z)>5).sum()}")
pz = act.assign(z=z).sort_values("z", ascending=False).head(3)
for _, rr in pz.iterrows():
    pv = stats.poisson.sf(rr.n - 1, m * rr.nact); kk = (act.nact == rr.nact).sum()
    print(f"   outlier nact={rr.nact:.0f} n={rr.n:.0f} z={rr.z:.2f}: P(X>=n)={pv:.2e}, esperado #clientes así con ese nact={pv*kk:.3f} (Bonferroni p={min(1,pv*len(act)):.3f})")
top = act.assign(z=z).sort_values("n", ascending=False).head(5)[["nact", "nprod", "n", "z"]]
print("top-5 clientes por #tx:", top.round(2).to_dict("records"))
sin = cst[cst.nact == 0]
print(f"clientes nact=0: {len(sin):,} ({len(sin)/len(cst):.2%}), con tx>0: {(sin.n>0).sum()}; sin ningún producto: {(cst.nprod==0).sum():,}")
r = np.corrcoef(cst.n, cst.nact)[0, 1]
r2_teo = (m ** 2 * cst.nact.var()) / (m ** 2 * cst.nact.var() + m * cst.nact.mean())
print(f"corr(ntx,nact)={r:.4f} R²={r**2:.4f}  techo teórico si ntx~Poisson(λ·nact)={r2_teo:.4f}")

print("\n=== D. Orden de generación (posición en archivo fuente) ===")
con.execute("""CREATE TEMP TABLE prow AS SELECT product_id, file_row_number frn FROM read_parquet('data/bronze/products.parquet', file_row_number=true)""")
print(Q("""SELECT decil, count(*) k, round(avg(n),3) media FROM (SELECT ntile(10) OVER (ORDER BY frn) decil, n FROM pn JOIN prow USING(product_id)
   WHERE pstatus='Active') GROUP BY 1 ORDER BY 1""").T.to_string())
print("spearman(n, fila producto):", round(F("SELECT corr(rank_n, rank_f) FROM (SELECT rank() OVER (ORDER BY n) rank_n, rank() OVER (ORDER BY frn) rank_f FROM pn JOIN prow USING(product_id) WHERE pstatus='Active')")[0][0], 5))

print("\n=== F. Utilidad: densidad temporal ===")
print(Q("""SELECT count(*) nprod, round(avg(n)/36.0,4) tx_mes, round(avg((d30>0)::INT),4) p_tx_30d, round(avg((d90>0)::INT),4) p_tx_90d,
   round(avg((d365>0)::INT),4) p_tx_365d, round(avg(d30),3) media_30d FROM pn WHERE pstatus='Active'""").to_string(index=False))
lam30 = m * 30 / 1097; lam90 = m * 90 / 1097
print(f"esperado Poisson: P(>=1 en 30d)={1-np.exp(-lam30):.4f}  P(>=1 en 90d)={1-np.exp(-lam90):.4f}")
print(Q("""SELECT count(*) nclientes_act, round(avg((s30>0)::INT),4) p_tx_30d, round(avg((s90>0)::INT),4) p_tx_90d FROM
   (SELECT customer_id, sum(d30) s30, sum(d90) s90 FROM pn WHERE pstatus='Active' GROUP BY 1)""").to_string(index=False))
print(Q("""SELECT CASE WHEN opened >= DATE '2026-01-01' THEN 'abierto 2026' WHEN opened >= DATE '2023-06-17' THEN 'abierto en ventana'
   ELSE 'abierto antes de ventana' END g, count(*) nprod, round(avg(n),3) tx, round(sum(pre)/sum(n),4) frac_tx_antes_apertura
   FROM pn WHERE pstatus='Active' GROUP BY 1 ORDER BY 1""").to_string(index=False))
print("fracción global de tx antes de la apertura del producto:", round(F("SELECT sum(pre)/sum(n) FROM pn")[0][0], 4))
