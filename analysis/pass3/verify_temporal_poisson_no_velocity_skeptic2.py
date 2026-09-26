"""Verificador escéptico (reintento) de 'temporal_poisson_no_velocity'. Parte 1.
Ángulos nuevos respecto del script original:
 1) reproducción base: conteo por producto (universo Active), por ptype, producto-mes con datos COMPLETOS
 2) ¿'homogéneo'? volumen diario por día de semana (process_date y ts) vs SD Poisson
 3) huella por cliente con tests más potentes que 'proporción': chi² multinomial por cliente para hora (24),
    día de semana (7), día del mes (31), mes (12); controles positivos (ttype) y otros (canal, estado).
    Bajo H0 (todos los clientes comparten la distribución global) E[chi²] = K-1 exactamente.
"""
import duckdb, pandas as pd, numpy as np
from scipy.stats import poisson, chi2 as chi2d
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()

print("== 1. conteo por producto ==")
print(q("""WITH a AS (SELECT product_id, count(*) n FROM tx GROUP BY 1)
  SELECT p.pstatus, count(*) prods, count(a.n) with_tx, round(avg(a.n),3) mean_n, round(var_samp(a.n),3) var_n,
         round(var_samp(a.n)/avg(a.n),4) disp, min(a.n) mn, max(a.n) mx
  FROM pr p LEFT JOIN a USING(product_id) GROUP BY 1 ORDER BY 1""").to_string(index=False))
print(q("""WITH a AS (SELECT product_id, count(*) n FROM tx GROUP BY 1)
  SELECT p.ptype, count(*) prods, round(avg(n),3) mean_n, round(var_samp(n)/avg(n),3) disp
  FROM a JOIN pr p USING(product_id) GROUP BY 1 ORDER BY 1""").to_string(index=False))
P = q("SELECT count(DISTINCT product_id) p FROM tx").p[0]
m = q("""WITH m AS (SELECT product_id, date_trunc('month', process_date) mo, count(*) k FROM tx
          WHERE process_date >= '2023-07-01' AND process_date < '2026-06-01' GROUP BY ALL)
         SELECT sum(k)::DOUBLE s1, sum(k*k)::DOUBLE s2, count(DISTINCT mo) M FROM m""")
M = int(m.M[0]); cells = P * M
mean_k = m.s1[0] / cells; var_k = m.s2[0] / cells - mean_k**2
print(f"producto-mes (P={P}, M={M}): media={mean_k:.4f} var={var_k:.4f} disp={var_k/mean_k:.4f}")

print("== 2. homogeneidad temporal (volumen diario) ==")
for col in ['process_date', 'ts::DATE']:
    d = q(f"""WITH d AS (SELECT {col} d, count(*) n FROM tx GROUP BY 1)
      SELECT dayname(d) dn, dayofweek(d) dw, count(*) ndays, round(avg(n),1) mean_n, round(stddev(n),1) sd_n,
             round(sqrt(avg(n)),1) sd_poisson FROM d WHERE d > DATE '2023-06-17' AND d < DATE '2026-06-17'
      GROUP BY ALL ORDER BY dw""")
    d['rel'] = (d.mean_n / d.mean_n[d.dw.between(1, 5)].mean()).round(3)
    print(f"-- por {col}"); print(d.to_string(index=False))
wk = q("""SELECT avg((dayofweek(process_date) IN (0,6))::INT) share_wkend FROM tx""")
print("share fin de semana (process_date):", round(wk.share_wkend[0], 4), " uniforme=2/7=0.2857")

print("== 3. huella por cliente / producto: chi² multinomial vs K-1 ==")
dims = {
    'hora(24)': "hour(ts)",
    'bloque6h(4)': "hour(ts - INTERVAL 6 HOUR)//6",
    'dia_semana(7)': "dayofweek(process_date)",
    'dia_mes(31)': "day(process_date)",
    'mes(12)': "month(process_date)",
    'canal': "channel",
    'estado': "status",
    'ttype [control+]': "ttype",
}
N = q("SELECT count(*) n FROM tx").n[0]
rows = []
for unit in ['customer_id', 'product_id']:
    for name, expr in dims.items():
        r = q(f"""WITH g AS (SELECT {expr} j, count(*)::DOUBLE / {N} p FROM tx GROUP BY 1),
          c AS (SELECT {unit} u, {expr} j, count(*)::DOUBLE k FROM tx GROUP BY ALL),
          n AS (SELECT {unit} u, count(*)::DOUBLE n FROM tx GROUP BY 1),
          s AS (SELECT c.u, sum(k*k/p) / any_value(n.n) - any_value(n.n) chi, any_value(n.n) n
                FROM c JOIN g USING(j) JOIN n USING(u) WHERE n.n >= 10 GROUP BY 1)
          SELECT count(*) units, avg(chi) mean_chi, stddev(chi) sd_chi, (SELECT count(*) FROM g) K FROM s""")
        K = int(r.K[0]); mc = r.mean_chi[0]; se = r.sd_chi[0] / np.sqrt(r.units[0])
        rows.append(dict(unidad=unit.split('_')[0], dim=name, K=K, n_units=int(r.units[0]), mean_chi=round(mc, 3),
                         esperado=K-1, ratio=round(mc/(K-1), 4), ic95=f"[{(mc-1.96*se)/(K-1):.4f},{(mc+1.96*se)/(K-1):.4f}]"))
print(pd.DataFrame(rows).to_string(index=False))
