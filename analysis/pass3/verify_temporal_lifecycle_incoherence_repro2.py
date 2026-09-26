"""Verificación independiente (repro2) de 'temporal_lifecycle_incoherence'.
Enfoque propio: además de contar, se compara lo observado con lo ESPERADO si las tx fueran
independientes del ciclo de vida (fechas de tx tomadas de la distribución diaria global de tx).
  E[# tx antes de opened]      = sum_p n_p * F(<opened_p)
  E[P(alguna tx antes de abrir)] = 1 - (1 - F(<opened_p))^n_p
Si observado/esperado ~ 1, las tx ignoran opened/expires/registration_date.
Definiciones: 'antes de abrir' = ts < opened (DATE -> medianoche) == ts::DATE < opened.
'después de vencer' variante A = ts > expires (medianoche, como el hallazgo); variante B = ts::DATE > expires.
"""
import duckdb, numpy as np, pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
con = duckdb.connect('data/analysis.duckdb', read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
q = lambda s: con.execute(s).fetchdf()
def pct(a, b): return f"{a:,}/{b:,} = {100*a/b:.2f}%"

print("== 0. ventana ==")
print(q("SELECT min(ts) ts_min, max(ts) ts_max, count(*) n FROM tx").to_string(index=False))

# ---------- CDF empírica diaria de tx ----------
con.execute("CREATE TEMP TABLE dcnt AS SELECT ts::DATE d, count(*) n FROM tx GROUP BY 1")
con.execute("""CREATE TEMP TABLE spine AS
WITH s AS (SELECT CAST(g AS DATE) d FROM generate_series(TIMESTAMP '2017-01-01', TIMESTAMP '2032-12-31', INTERVAL 1 DAY) t(g)),
j AS (SELECT s.d, coalesce(dc.n,0) n FROM s LEFT JOIN dcnt dc USING(d)),
tot AS (SELECT sum(n)::DOUBLE N FROM dcnt)
SELECT d, (sum(n) OVER (ORDER BY d) - n)/(SELECT N FROM tot) F_lt, sum(n) OVER (ORDER BY d)/(SELECT N FROM tot) F_le FROM j""")

# volumen por semestre (si las tx respetaran opened, crecería con la base de productos abiertos)
print("\n== 0b. volumen de tx por semestre (vs productos abiertos acumulados) ==")
print(q("""WITH v AS (SELECT year(d)*10 + (CASE WHEN month(d)<=6 THEN 1 ELSE 2 END) sem, sum(n) n_tx, count(*) dias FROM dcnt GROUP BY 1),
 o AS (SELECT year(opened)*10 + (CASE WHEN month(opened)<=6 THEN 1 ELSE 2 END) sem, count(*) n_open FROM pr WHERE pstatus='Active' GROUP BY 1)
 SELECT v.sem, v.n_tx, v.dias, round(v.n_tx/v.dias) tx_por_dia,
   (SELECT count(*) FROM pr WHERE pstatus='Active' AND opened <= make_date(v.sem//10, CASE WHEN v.sem%10=1 THEN 6 ELSE 12 END, 28)) activos_abiertos_al_cierre
 FROM v ORDER BY 1""").to_string(index=False))

print("\n== 1. nivel tx: antes de apertura / después de vencimiento ==")
r = q("""SELECT count(*) n_tx, count(p.product_id) n_match,
  sum((t.ts < p.opened)::INT) n_bo, sum((t.ts::DATE < p.opened)::INT) n_bo_d,
  sum((p.ptype LIKE 'Tarjeta%')::INT) n_card, sum((p.expires IS NOT NULL)::INT) n_withexp,
  sum((p.expires IS NOT NULL AND p.ptype NOT LIKE 'Tarjeta%')::INT) n_withexp_noncard,
  sum(coalesce(t.ts > p.expires,false)::INT) n_ae_A, sum(coalesce(t.ts::DATE > p.expires,false)::INT) n_ae_B,
  sum((t.ts < p.opened OR coalesce(t.ts > p.expires,false))::INT) n_out_A,
  sum((t.ts < p.opened OR coalesce(t.ts::DATE > p.expires,false))::INT) n_out_B,
  sum((t.ts < p.opened AND coalesce(t.ts > p.expires,false))::INT) n_both
  FROM tx t LEFT JOIN pr p USING(product_id)""").iloc[0]
r = {k: int(v) for k, v in r.items()}
print(r)
print("antes de opened:", pct(r['n_bo'], r['n_tx']))
print("después de expires (A: ts>expires) sobre tx con expires:", pct(r['n_ae_A'], r['n_withexp']), "| sobre TODAS las tx con tarjeta:", pct(r['n_ae_A'], r['n_card']))
print("después de expires (B: fecha>expires):", pct(r['n_ae_B'], r['n_withexp']))
print("fuera de la vida (A):", pct(r['n_out_A'], r['n_tx']), "| (B):", pct(r['n_out_B'], r['n_tx']))

print("\n== 2. esperado bajo independencia (CDF diaria global) ==")
con.execute("""CREATE TEMP TABLE pa AS
SELECT t.product_id, count(*) n, min(t.ts) f, max(t.ts) l,
  sum((t.ts < p.opened)::INT) n_bo, sum(coalesce(t.ts > p.expires,false)::INT) n_aeA, sum(coalesce(t.ts::DATE > p.expires,false)::INT) n_aeB
FROM tx t JOIN pr p USING(product_id) GROUP BY 1""")
e = q("""SELECT count(*) n_prod, sum(a.n) n_tx,
  sum(a.n_bo) obs_bo, sum(a.n * so.F_lt) exp_bo, sum(a.n * so.F_lt*(1-so.F_lt)) var_bo,
  sum((a.n_bo>0)::INT) obs_prod_any_bo, sum(1 - pow(1 - so.F_lt, a.n)) exp_prod_any_bo,
  sum(a.n) FILTER (WHERE p.expires IS NOT NULL) n_tx_exp,
  sum(a.n_aeA) obs_aeA, sum(a.n * (1 - se.F_lt)) FILTER (WHERE p.expires IS NOT NULL) exp_aeA,
  sum(a.n_aeB) obs_aeB, sum(a.n * (1 - se.F_le)) FILTER (WHERE p.expires IS NOT NULL) exp_aeB
FROM pa a JOIN pr p USING(product_id) JOIN spine so ON so.d = p.opened LEFT JOIN spine se ON se.d = p.expires""").iloc[0]
print(e.to_string())
print(f"tx antes de abrir: obs/esp = {e.obs_bo:,.0f}/{e.exp_bo:,.0f} = {e.obs_bo/e.exp_bo:.4f} (z={(e.obs_bo-e.exp_bo)/np.sqrt(e.var_bo):.2f})")
print(f"productos con alguna tx antes de abrir: obs {e.obs_prod_any_bo/e.n_prod:.4f} vs esp {e.exp_prod_any_bo/e.n_prod:.4f} (n={int(e.n_prod):,})")
print(f"tx tras vencer A: obs/esp = {e.obs_aeA:,.0f}/{e.exp_aeA:,.0f} = {e.obs_aeA/e.exp_aeA:.4f}; B: {e.obs_aeB:,.0f}/{e.exp_aeB:,.0f} = {e.obs_aeB/e.exp_aeB:.4f}")

print("\n== 2b. obs/esp de tx antes de abrir por año de apertura (productos con tx) ==")
print(q("""SELECT year(p.opened) y, count(*) n_prod, round(avg(a.n),2) avg_tx, sum(a.n_bo) obs_bo, round(sum(a.n*so.F_lt)) exp_bo,
  round(sum(a.n_bo)/nullif(sum(a.n*so.F_lt),0),4) ratio,
  round(avg((a.f < p.opened)::INT),4) first_before_open, round(avg(1-pow(1-so.F_lt,a.n)),4) exp_first_before_open
  FROM pa a JOIN pr p USING(product_id) JOIN spine so ON so.d=p.opened GROUP BY 1 ORDER BY 1""").to_string(index=False))

print("\n== 3. productos abiertos dentro vs antes de la ventana ==")
print(q("""SELECT (p.opened >= DATE '2023-06-17') abierto_en_ventana, count(*) n_prod, round(avg(a.n),3) avg_tx,
  round(avg((a.f < p.opened)::INT),4) first_before_open, round(avg(1-pow(1-so.F_lt,a.n)),4) esperado_indep,
  round(avg((a.n_bo>0)::INT),4) any_before_open
  FROM pa a JOIN pr p USING(product_id) JOIN spine so ON so.d=p.opened GROUP BY 1 ORDER BY 1""").to_string(index=False))
print(q("""SELECT pstatus, count(*) n_prod, sum((a.product_id IS NOT NULL)::INT) n_con_tx FROM pr p LEFT JOIN pa a USING(product_id) GROUP BY 1 ORDER BY 1""").to_string(index=False))

print("\n== 4. tasa de rechazo / código 54 dentro vs fuera de la vida ==")
g = q("""SELECT (t.ts < p.opened) antes_abrir, coalesce(t.ts > p.expires,false) tras_vencer, (p.expires IS NOT NULL) tiene_exp, count(*) n,
  sum((t.status='Declined')::INT) decl, sum((t.status='Approved')::INT) appr, sum(t.fraud::INT) fraud,
  sum((t.code='54')::INT) c54, sum((t.code='54' AND t.status='Declined')::INT) c54_decl
  FROM tx t JOIN pr p USING(product_id) GROUP BY ALL""")
g['outside'] = g.antes_abrir | g.tras_vencer
def rr(sub, col):
    o = sub[sub.outside]; i = sub[~sub.outside]
    a, n1, b, n0 = o[col].sum(), o.n.sum(), i[col].sum(), i.n.sum()
    p1, p0 = a/n1, b/n0; ratio = p1/p0
    se = np.sqrt(1/a - 1/n1 + 1/b - 1/n0)
    return f"{col}: fuera {a:,}/{n1:,}={100*p1:.3f}% | dentro {b:,}/{n0:,}={100*p0:.3f}% | RR={ratio:.4f} IC95 [{ratio*np.exp(-1.96*se):.4f}, {ratio*np.exp(1.96*se):.4f}]"
for col in ['decl', 'appr', 'fraud', 'c54']:
    print("todas:", rr(g, col))
cards = g[g.tiene_exp].copy(); cards['outside'] = cards.tras_vencer
for col in ['decl', 'c54', 'c54_decl']:
    print("tarjetas con expires, tras vencer vs vigentes:", rr(cards, col))
print(g.groupby(['antes_abrir', 'tras_vencer'])[['n', 'decl', 'c54']].sum().assign(decl_rate=lambda d: (d.decl/d.n).round(5), c54_rate=lambda d: (d.c54/d.n).round(5)).to_string())

print("\n== 5. pr.last_tx vs max(ts) de tx ==")
print(q("""SELECT count(*) n_prod_tx, count(p.last_tx) n_lt, count(*) - count(p.last_tx) prod_con_tx_sin_last_tx,
  sum((p.last_tx = a.l)::INT) eq_ts, round(avg((p.last_tx::DATE = a.l::DATE)::INT),5) eq_date,
  sum((p.last_tx < p.opened)::INT) lt_before_open, round(avg((p.last_tx > a.l)::INT),4) lt_after_maxts,
  round(avg((p.last_tx < TIMESTAMP '2023-06-17 06:00:00')::INT),4) lt_before_window,
  quantile_cont(date_diff('day', a.l, p.last_tx), [0.1,0.5,0.9]) q_dias,
  quantile_cont(epoch(p.last_tx - a.l)/86400.0, [0.1,0.5,0.9]) q_dias_epoch
  FROM pa a JOIN pr p USING(product_id)""").T.to_string())
# ¿last_tx ~ U(opened, fin)?
print(q("""SELECT quantile_cont(epoch(last_tx - opened::TIMESTAMP)/epoch(TIMESTAMP '2026-06-18 00:00:00' - opened::TIMESTAMP), [0.1,0.25,0.5,0.75,0.9]) u_lasttx_entre_opened_y_fin,
  corr(epoch(last_tx), epoch(opened::TIMESTAMP)) corr_lt_opened FROM pr WHERE last_tx IS NOT NULL AND opened < DATE '2026-06-10'""").T.to_string())
print(q("""SELECT (p.last_tx IS NULL) lt_null, count(*) n, round(avg(a.n),3) avg_tx FROM pa a JOIN pr p USING(product_id) GROUP BY 1""").to_string(index=False))

print("\n== 6. clientes: tx antes de registration_date ==")
con.execute("CREATE TEMP TABLE ca AS SELECT customer_id, count(*) n, min(ts) f FROM tx GROUP BY 1")
c = q("""SELECT count(*) n_cust, count(cu.customer_id) n_match, sum((ca.f < cu.registration_date)::INT) obs_first_before_reg,
  sum(1 - pow(1 - s.F_lt, ca.n)) exp_first_before_reg,
  sum((cu.registration_date >= TIMESTAMP '2023-06-17')::INT) reg_en_ventana
  FROM ca LEFT JOIN cu USING(customer_id) LEFT JOIN spine s ON s.d = cu.registration_date::DATE""").iloc[0]
print(c.to_string())
print("clientes con primera tx antes del registro:", pct(int(c.obs_first_before_reg), int(c.n_cust)), f"| esperado indep {c.exp_first_before_reg/c.n_cust:.4f}")
t = q("""SELECT count(*) n, sum((t.ts < cu.registration_date)::INT) obs, sum(s.F_lt) esp
  FROM tx t JOIN cu USING(customer_id) JOIN spine s ON s.d = cu.registration_date::DATE""").iloc[0]
print(f"tx antes del registro: {int(t.obs):,}/{int(t.n):,} = {t.obs/t.n:.4f}; esperado indep (día) {t.esp/t.n:.4f}; obs/esp {t.obs/t.esp:.4f}")

print("\n== 7. last_updated en el futuro ==")
for lab, end in [("fin_tx 2026-06-18 06:00", "TIMESTAMP '2026-06-18 06:00:00'"), ("2026-06-17 23:59:59", "TIMESTAMP '2026-06-17 23:59:59'")]:
    print(lab, q(f"""SELECT (SELECT count(*) FROM pr) n_pr, (SELECT sum((last_updated > {end})::INT) FROM pr) pr_fut,
      (SELECT round(avg((last_updated > {end})::INT),4) FROM pr) pr_share, (SELECT max(last_updated) FROM pr) pr_max,
      (SELECT count(*) FROM cu) n_cu, (SELECT sum((last_updated > {end})::INT) FROM cu) cu_fut,
      (SELECT round(avg((last_updated > {end})::INT),4) FROM cu) cu_share, (SELECT max(last_updated) FROM cu) cu_max""").to_string(index=False))

print("\n== 8. estado de productos con tx; Active vencidos ==")
print(q("SELECT p.pstatus, count(*) n_tx FROM tx t JOIN pr p USING(product_id) GROUP BY 1").to_string(index=False))
print(q("""SELECT pstatus, count(*) n, count(expires) n_con_exp,
  sum((expires < DATE '2026-06-17')::INT) n_vencidos,
  round(sum((expires < DATE '2026-06-17')::INT)/count(expires),4) venc_sobre_con_exp,
  round(sum((expires < DATE '2026-06-17')::INT)/count(*),4) venc_sobre_todos
  FROM pr GROUP BY 1 ORDER BY 1""").to_string(index=False))
print(q("""SELECT ptype, count(*) n, round(avg((expires IS NOT NULL)::INT),4) share_con_exp FROM pr WHERE ptype LIKE 'Tarjeta%' GROUP BY 1""").to_string(index=False))
