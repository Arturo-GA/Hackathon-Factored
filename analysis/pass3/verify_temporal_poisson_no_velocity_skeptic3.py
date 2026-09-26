"""Verificador escéptico (reintento) de 'temporal_poisson_no_velocity'. Parte 2 (datos completos).
 4) regularidad escondida: picos en el histograma de intervalos por día (7/14/15/30 días) en todos los intervalos
    y en secuencias Payment de préstamos / Deposit de cuentas (cuotas, nómina); CV por familia x ttype
 5) velocidad -> resultado: tasa de rechazo / fraude / fscore>=50 por intervalo previo (producto y cliente)
 6) ráfagas entre productos del mismo cliente vs esperado por colocación uniforme
 7) fraude: siguiente tx tras fraude (z-test), Markov de estado, agrupamiento comercio-día / ciudad-día / sucursal-día
"""
import duckdb, pandas as pd, numpy as np
from scipy.stats import norm
pd.set_option('display.width', 250)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
FAM = """CASE WHEN p.ptype LIKE 'Préstamo%' THEN 'prestamo' WHEN p.ptype LIKE 'Cuenta%' THEN 'cuenta'
              WHEN p.ptype LIKE 'Tarjeta%' THEN 'tarjeta' ELSE 'inv_seg' END"""

def spikes(h, label):
    h = h.set_index('d').n.reindex(range(0, 61), fill_value=0).astype(float)
    out = []
    for d in range(3, 58):
        nb = [h[d+k] for k in (-3, -2, -1, 1, 2, 3)]
        out.append((d, h[d], h[d] / np.mean(nb)))
    o = pd.DataFrame(out, columns=['d', 'n', 'ratio'])
    o['z'] = (o.n - o.n / o.ratio) / np.sqrt(o.n / o.ratio)
    top = o.reindex(o.z.abs().sort_values(ascending=False).index).head(4)
    sel = o[o.d.isin([7, 14, 15, 28, 29, 30, 31])]
    print(f"  [{label}] días con n={int(h.sum())}: max|z|={o.z.abs().max():.2f} (esperable ~2.9 con 55 pruebas); "
          f"ratio en d=7,14,15,28-31: {dict(zip(sel.d, sel.ratio.round(3)))}; top: {dict(zip(top.d, top.ratio.round(3)))}")

print("== 4. regularidad escondida ==")
h = q("""WITH g AS (SELECT date_diff('second', lag(ts) OVER (PARTITION BY product_id ORDER BY ts), ts) gap FROM tx)
         SELECT (gap // 86400)::INT d, count(*) n FROM g WHERE gap IS NOT NULL AND gap < 61*86400 GROUP BY 1""")
spikes(h, 'todos los intervalos por producto')
cv = q(f"""WITH t AS (SELECT t.product_id, t.ts, t.ttype, {FAM} fam FROM tx t JOIN pr p USING(product_id)),
  g AS (SELECT fam, ttype, date_diff('second', lag(ts) OVER (PARTITION BY product_id, ttype ORDER BY ts), ts) gap FROM t)
  SELECT fam, ttype, count(gap) n_gaps, round(avg(gap)/86400,1) mean_days, round(stddev(gap)/avg(gap),3) cv,
         round(avg((gap < 86400*1.0)::INT)*100,3) pct_lt1d
  FROM g WHERE gap IS NOT NULL GROUP BY ALL ORDER BY fam, ttype""")
print(cv.to_string(index=False))
for fam, tt in [('prestamo', 'Payment'), ('cuenta', 'Deposit'), ('tarjeta', 'Payment')]:
    h = q(f"""WITH t AS (SELECT t.product_id, t.ts, t.ttype, {FAM} fam FROM tx t JOIN pr p USING(product_id) WHERE t.ttype='{tt}'),
      g AS (SELECT date_diff('second', lag(ts) OVER (PARTITION BY product_id ORDER BY ts), ts) gap FROM t WHERE fam='{fam}')
      SELECT (gap // 86400)::INT d, count(*) n FROM g WHERE gap IS NOT NULL AND gap < 61*86400 GROUP BY 1""")
    spikes(h, f'{fam}/{tt}')
# concentración por día del mes de Payment en préstamos (cuota fija el mismo día)
dm = q(f"""WITH t AS (SELECT t.product_id, day(t.process_date) j FROM tx t JOIN pr p USING(product_id)
              WHERE t.ttype='Payment' AND {FAM}='prestamo'),
  g AS (SELECT j, count(*)::DOUBLE / (SELECT count(*) FROM t) p FROM t GROUP BY 1),
  c AS (SELECT product_id, j, count(*)::DOUBLE k FROM t GROUP BY ALL),
  n AS (SELECT product_id, count(*)::DOUBLE n FROM t GROUP BY 1),
  s AS (SELECT c.product_id, sum(k*k/p)/any_value(n.n) - any_value(n.n) chi FROM c JOIN g USING(j) JOIN n USING(product_id)
        WHERE n.n >= 5 GROUP BY 1)
  SELECT count(*) prods, avg(chi) mean_chi, stddev(chi)/sqrt(count(*)) se FROM s""")
print(f"  préstamos Payment, día del mes por producto (>=5 pagos): chi² medio {dm.mean_chi[0]:.3f} vs 30 esperado "
      f"(ratio {dm.mean_chi[0]/30:.4f} ± {1.96*dm.se[0]/30:.4f}), prods={dm.prods[0]}")

print("== 5. velocidad -> resultado ==")
B = """CASE WHEN gap IS NULL THEN '0_primera' WHEN gap<3600 THEN 'a<1h' WHEN gap<86400 THEN 'b<1d' WHEN gap<7*86400 THEN 'c<7d'
          WHEN gap<30*86400 THEN 'd<30d' WHEN gap<90*86400 THEN 'e<90d' ELSE 'f>=90d' END"""
for part in ['product_id', 'customer_id']:
    v = q(f"""WITH g AS (SELECT status, fraud, fscore, date_diff('second', lag(ts) OVER (PARTITION BY {part} ORDER BY ts), ts) gap FROM tx)
      SELECT {B} b, count(*) n, round(avg((status='Declined')::INT)*100,2) pct_decl, sum(fraud::INT) n_fraud,
             round(avg(fraud::INT)*1000,3) fraud_x1000, round(avg((fscore>=50)::INT)*100,3) pct_fs50
      FROM g GROUP BY 1 ORDER BY 1""")
    print(f"-- intervalo previo dentro de {part}"); print(v.to_string(index=False))
# conteo de tx del cliente en las 24 h / 7 d previas
v = q("""WITH w AS (SELECT status, fraud,
          count(*) OVER (PARTITION BY customer_id ORDER BY ts RANGE BETWEEN INTERVAL 1 DAY PRECEDING AND CURRENT ROW) - 1 n24,
          count(*) OVER (PARTITION BY customer_id ORDER BY ts RANGE BETWEEN INTERVAL 7 DAY PRECEDING AND CURRENT ROW) - 1 n7d FROM tx)
   SELECT least(n7d, 3) n7d_cap, count(*) n, round(avg((status='Declined')::INT)*100,2) pct_decl, sum(fraud::INT) n_fraud,
          round(avg(fraud::INT)*1000,3) fraud_x1000, sum((n24>0)::INT) with_prev24h FROM w GROUP BY 1 ORDER BY 1""")
print("-- tx previas del cliente en 7 días"); print(v.to_string(index=False))

print("== 6. ráfagas entre productos del mismo cliente ==")
T = (pd.Timestamp('2026-06-18 06:00') - pd.Timestamp('2023-06-17 06:00')).total_seconds()
gc = q("""WITH g AS (SELECT product_id, lag(product_id) OVER w pp,
             date_diff('second', lag(ts) OVER w, ts) gap FROM tx WINDOW w AS (PARTITION BY customer_id ORDER BY ts))
   SELECT (pp = product_id) same_prod, count(gap) n, sum((gap=0)::INT) s0, sum((gap<60)::INT) lt60, sum((gap<3600)::INT) lt1h,
          sum((gap<86400)::INT) lt1d FROM g WHERE gap IS NOT NULL GROUP BY 1""")
print(gc.to_string(index=False))
hn = q("SELECT n, count(*) k FROM (SELECT customer_id, count(*) n FROM tx GROUP BY 1) GROUP BY 1")
tot = gc.sum(numeric_only=True)
for s, col in [(1, 's0'), (60, 'lt60'), (3600, 'lt1h'), (86400, 'lt1d')]:
    e = (hn.k * (hn.n - 1) * (1 - (1 - s / T) ** hn.n)).sum()
    print(f"  cliente gaps<{s}s: obs={int(tot[col])} esperado_uniforme={e:.1f} razón={tot[col]/e:.3f}")

print("== 7. fraude ==")
f = q("""WITH s AS (SELECT fraud, status, lead(ts) OVER w nts, lead(status) OVER w ns, lead(fraud) OVER w nf, ts
             FROM tx WINDOW w AS (PARTITION BY product_id ORDER BY ts))
   SELECT fraud, count(*) n, count(nts) with_next, median(date_diff('second', ts, nts))/86400 med_days_next,
          sum((ns='Declined')::INT) next_decl, sum(nf::INT) next_fraud,
          sum((status='Declined')::INT) own_decl FROM s GROUP BY 1""")
print(f.to_string(index=False))
fr = f[f.fraud == True].iloc[0]; nf = f[f.fraud == False].iloc[0]
p0 = nf.next_decl / nf.with_next; p1 = fr.next_decl / fr.with_next
z = (p1 - p0) / np.sqrt(p0 * (1 - p0) / fr.with_next)
print(f"  siguiente rechazo tras fraude {p1:.4f} vs tras no-fraude {p0:.4f}: razón {p1/p0:.3f}, z={z:.2f}, p={2*norm.sf(abs(z)):.4f}")
q0 = nf.next_fraud / nf.with_next; q1 = fr.next_fraud / fr.with_next
print(f"  siguiente fraude tras fraude {q1*100:.3f}% ({int(fr.next_fraud)}/{int(fr.with_next)}) vs {q0*100:.3f}%: "
      f"esperados {q0*fr.with_next:.1f}")
print("  estado propio de la tx fraudulenta: Declined", round(fr.own_decl / fr.n, 4), "vs no fraude", round(nf.own_decl / nf.n, 4))
mk = q("""WITH s AS (SELECT status, lag(status) OVER (PARTITION BY product_id ORDER BY ts) ps FROM tx)
   SELECT ps, count(*) n, round(avg((status='Declined')::INT),4) p_decl FROM s WHERE ps IS NOT NULL GROUP BY 1 ORDER BY 1""")
print(mk.to_string(index=False))
Ntx, F = q("SELECT count(*)::DOUBLE, sum(fraud::INT)::DOUBLE FROM tx").iloc[0]
pp = F * (F - 1) / (Ntx * (Ntx - 1))
for name, key in [('comercio-día', "merchant_name, process_date"), ('ciudad-día', "city, process_date"),
                  ('sucursal-día', "branch_id, process_date"), ('cliente', "customer_id"), ('producto', "product_id"),
                  ('día', "process_date")]:
    r = q(f"""WITH c AS (SELECT {key}, count(*)::DOUBLE n, sum(fraud::INT)::DOUBLE f FROM tx
              WHERE {key.split(',')[0]} IS NOT NULL GROUP BY ALL)
         SELECT sum(n*(n-1)/2) pairs, sum(f*(f-1)/2) fpairs, sum(n) ntx, sum(f) nf, count(*) cells FROM c""").iloc[0]
    pp_sub = r.nf * (r.nf - 1) / (r.ntx * (r.ntx - 1))
    e = r.pairs * pp_sub
    print(f"  pares de fraudes en misma celda {name}: obs={int(r.fpairs)} esperado={e:.1f} razón={r.fpairs/e:.3f} (celdas={int(r.cells)})")
