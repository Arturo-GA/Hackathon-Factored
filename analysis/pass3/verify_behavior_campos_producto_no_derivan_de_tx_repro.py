"""Verificación independiente del hallazgo behavior_campos_producto_no_derivan_de_tx.

Reproduce: (1) pr.last_tx vs MAX/MIN(tx.ts) por producto; (2) pr.bal vs flujos de tx (corr, R² multivariado);
(3) hipotecas bal > credit_limit; (4) tx fuera del ciclo de vida del producto/cliente, comparando lo observado con
lo esperado si las tx fueran uniformes en la ventana 2023-06-17 → 2026-06-18 sin importar las fechas;
(5) productos abiertos antes del registro del cliente; (6) last_updated futuro; (7) tasas de rechazo/código 54/fraude
dentro y fuera de la vigencia.

Ejecutar: PYTHONIOENCODING=utf-8 .venv/Scripts/python analysis/pass3/verify_behavior_campos_producto_no_derivan_de_tx_repro.py
"""
import duckdb
import numpy as np
import pandas as pd

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 100)

con = duckdb.connect("data/analysis.duckdb", read_only=True)
con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")


def q(sql):
    return con.execute(sql).df()


def hdr(t):
    print("\n" + "=" * 8 + " " + t + " " + "=" * 8)


W0, W1 = "TIMESTAMP '2023-06-17 00:00:00'", "TIMESTAMP '2026-06-18 06:00:00'"
REF = "DATE '2026-06-17'"

# ---------------------------------------------------------------- agregados por producto
con.execute("""
CREATE TEMP TABLE agg AS
SELECT product_id,
       count(*) n, min(ts) mn, max(ts) mx,
       max(CASE WHEN status='Approved' THEN ts END) mx_ok,
       sum(CASE WHEN ttype='Deposit' THEN amount ELSE 0 END) dep,
       sum(CASE WHEN ttype='Withdrawal' THEN amount ELSE 0 END) wdr,
       sum(CASE WHEN ttype='Purchase' THEN amount ELSE 0 END) pur,
       sum(CASE WHEN ttype='Payment' THEN amount ELSE 0 END) pay,
       sum(CASE WHEN ttype='Transfer' THEN amount ELSE 0 END) trf,
       sum(CASE WHEN ttype='Adjustment' THEN amount ELSE 0 END) adj,
       sum(CASE WHEN status='Approved' AND ttype='Deposit' THEN amount ELSE 0 END) dep_ok,
       sum(CASE WHEN status='Approved' AND ttype IN ('Withdrawal','Purchase','Payment','Transfer') THEN amount ELSE 0 END) out_ok
FROM tx GROUP BY 1
""")

hdr("1. last_tx vs actividad real (productos Active con tx)")
print(q(f"""
SELECT count(*) n_active_con_tx,
  (SELECT count(*) FROM pr WHERE pstatus='Active') n_active_total,
  avg((p.last_tx IS NULL)::INT) share_lt_null,
  count(p.last_tx) n_lt_nonnull,
  avg(CASE WHEN p.last_tx IS NOT NULL THEN (abs(date_diff('day', a.mx::DATE, p.last_tx::DATE))<=1)::INT END) match_le1d_date,
  avg(CASE WHEN p.last_tx IS NOT NULL THEN (abs(epoch(p.last_tx)-epoch(a.mx))<=86400)::INT END) match_le24h,
  avg(CASE WHEN p.last_tx IS NOT NULL THEN (abs(epoch(p.last_tx)-epoch(a.mx_ok))<=86400)::INT END) match_le24h_approved,
  avg(CASE WHEN p.last_tx IS NOT NULL THEN (p.last_tx = a.mx)::INT END) exact_eq,
  corr(epoch(p.last_tx), epoch(a.mx)) pearson_lt_mx,
  avg(CASE WHEN p.last_tx IS NOT NULL THEN (p.last_tx < a.mn)::INT END) lt_before_first_tx,
  avg(CASE WHEN p.last_tx IS NOT NULL THEN (p.last_tx > a.mx)::INT END) lt_after_last_tx,
  median(date_diff('day', p.last_tx::DATE, {REF})) med_days_since_lasttx,
  median(date_diff('day', a.mx::DATE, {REF})) med_days_since_maxts,
  avg(CASE WHEN p.last_tx IS NOT NULL THEN (p.last_tx::DATE >= p.opened)::INT END) lt_ge_opened,
  avg(CASE WHEN p.last_tx IS NOT NULL THEN (p.last_tx < {W0})::INT END) lt_before_window
FROM pr p JOIN agg a USING(product_id) WHERE p.pstatus='Active'
""").T)

# rank correlation (Spearman) on non-null
print(q("""
WITH b AS (SELECT epoch(p.last_tx) x, epoch(a.mx) y FROM pr p JOIN agg a USING(product_id) WHERE p.pstatus='Active' AND p.last_tx IS NOT NULL),
r AS (SELECT rank() OVER (ORDER BY x) rx, rank() OVER (ORDER BY y) ry FROM b)
SELECT corr(rx, ry) spearman_lt_mx FROM r
""").T)

# restringiendo a last_tx dentro de la ventana de tx (para descartar que la corr baja se deba solo a last_tx pre-2023)
print(q(f"""
SELECT count(*) n_lt_in_window, corr(epoch(p.last_tx), epoch(a.mx)) pearson_in_window,
  avg((abs(epoch(p.last_tx)-epoch(a.mx))<=86400)::INT) match_le24h_in_window
FROM pr p JOIN agg a USING(product_id) WHERE p.pstatus='Active' AND p.last_tx >= {W0}
""").T)

# ¿last_tx coincide con el ts de ALGUNA tx del mismo cliente (posible permutación de product_id)?
print(q("""
WITH lt AS (SELECT customer_id, last_tx FROM pr WHERE last_tx IS NOT NULL),
m AS (SELECT DISTINCT lt.customer_id, lt.last_tx FROM lt JOIN tx t ON t.customer_id=lt.customer_id AND abs(epoch(t.ts)-epoch(lt.last_tx))<=60)
SELECT (SELECT count(*) FROM lt) n_lt, count(*) n_match_same_customer_60s FROM m
""").T)

hdr("1b. Nulidad de last_tx por pstatus")
print(q("""SELECT pstatus, count(*) n, avg((last_tx IS NULL)::INT) share_null,
  sum((product_id IN (SELECT product_id FROM agg))::INT) n_with_tx FROM pr GROUP BY 1 ORDER BY 2 DESC"""))

hdr("2. bal vs flujos de tx (por ptype x moneda)")
bal = q("""
SELECT p.ptype, p.currency, count(*) n,
  corr(p.bal, a.dep - (a.wdr+a.pur+a.pay+a.trf)) c_net_all,
  corr(p.bal, a.dep_ok - a.out_ok) c_net_ok,
  corr(p.bal, (a.wdr+a.pur+a.pay+a.trf) - a.dep) c_debt_like,
  stddev(p.bal) sd_bal, stddev(a.dep - (a.wdr+a.pur+a.pay+a.trf)) sd_net
FROM pr p JOIN agg a USING(product_id) GROUP BY 1,2 ORDER BY 1,2""")
print(bal.round(4))
b2 = bal.dropna(subset=["c_net_all"])
print(f"combos con corr definida: {len(b2)} de {len(bal)}; rango c_net_all [{b2.c_net_all.min():.4f}, {b2.c_net_all.max():.4f}]; "
      f"rango c_net_ok [{b2.c_net_ok.min():.4f}, {b2.c_net_ok.max():.4f}]")
print(q("SELECT ptype, count(*) n, min(bal), max(bal), avg((bal=0)::INT) share_zero FROM pr WHERE ptype='Seguro' GROUP BY 1"))

# R² multivariado (bal ~ sumas por ttype + n) con log1p y lineal, por ptype x moneda, OOS 50/50
d = q("""SELECT p.ptype, p.currency, p.bal, a.n, a.dep, a.wdr, a.pur, a.pay, a.trf, a.adj, a.dep_ok, a.out_ok
         FROM pr p JOIN agg a USING(product_id) WHERE p.ptype <> 'Seguro'""")
rng = np.random.default_rng(0)
rows = []
for (pt, cur), g in d.groupby(["ptype", "currency"]):
    X = g[["n", "dep", "wdr", "pur", "pay", "trf", "adj", "dep_ok", "out_ok"]].to_numpy(float)
    y = g["bal"].to_numpy(float)
    for tag, XX, yy in [("lin", X, y), ("log", np.log1p(np.abs(X)), np.sign(y) * np.log1p(np.abs(y)))]:
        idx = rng.permutation(len(yy)); h = len(yy) // 2
        tr, te = idx[:h], idx[h:]
        A = np.c_[np.ones(len(yy)), XX]
        beta, *_ = np.linalg.lstsq(A[tr], yy[tr], rcond=None)
        pred = A[te] @ beta
        r2 = 1 - np.sum((yy[te] - pred) ** 2) / np.sum((yy[te] - yy[te].mean()) ** 2)
        rows.append((pt, cur, tag, len(yy), r2))
r2 = pd.DataFrame(rows, columns=["ptype", "cur", "spec", "n", "R2_oos"])
print(r2.pivot_table(index=["ptype", "cur"], columns="spec", values="R2_oos").round(4))
print("R2_oos max:", r2.R2_oos.max().round(4))

hdr("3. Hipotecas: bal > credit_limit")
print(q("""SELECT count(*) n, count(credit_limit) n_cl_nonnull,
  avg(CASE WHEN credit_limit IS NOT NULL THEN (bal > credit_limit)::INT END) share_bal_gt_cl_nonnull,
  sum((bal > credit_limit)::INT)*1.0/count(*) share_bal_gt_cl_all
FROM pr WHERE ptype='Préstamo Hipotecario'"""))
print(q("""SELECT ptype, count(credit_limit) n_cl, avg(CASE WHEN credit_limit IS NOT NULL THEN (bal > credit_limit)::INT END) share_bal_gt_cl
FROM pr GROUP BY 1 HAVING count(credit_limit)>0 ORDER BY 1"""))

hdr("4a. tx antes de la apertura del producto (nivel tx) + esperado bajo uniformidad")
# esperado: fracción de la ventana [W0,W1] anterior a opened (acotado 0..1)
print(q(f"""
SELECT count(*) n_tx, avg((t.ts::DATE < p.opened)::INT) obs_before_open,
  avg(greatest(0, least(1, (epoch(p.opened::TIMESTAMP) - epoch({W0})) / (epoch({W1}) - epoch({W0}))))) exp_uniform
FROM tx t JOIN pr p USING(product_id)"""))
print(q(f"""
SELECT year(p.opened) y_open, count(*) n_tx, count(DISTINCT p.product_id) n_prod,
  round(100*avg((t.ts::DATE < p.opened)::INT),1) obs_pct,
  round(100*avg(greatest(0, least(1, (epoch(p.opened::TIMESTAMP) - epoch({W0})) / (epoch({W1}) - epoch({W0}))))),1) exp_pct
FROM tx t JOIN pr p USING(product_id) GROUP BY 1 ORDER BY 1"""))
# densidad de tx por producto-día antes vs después de la apertura (productos abiertos dentro de la ventana)
print(q(f"""
WITH pp AS (SELECT p.product_id, p.opened,
   greatest(0, date_diff('day', DATE '2023-06-17', p.opened)) days_pre,
   greatest(0, date_diff('day', p.opened, DATE '2026-06-17')) days_post
 FROM pr p WHERE p.opened > DATE '2023-06-17' AND p.product_id IN (SELECT product_id FROM agg)),
c AS (SELECT t.product_id, sum((t.ts::DATE < pp.opened)::INT) n_pre, sum((t.ts::DATE >= pp.opened)::INT) n_post FROM tx t JOIN pp USING(product_id) GROUP BY 1)
SELECT count(*) n_prod, sum(n_pre)/sum(days_pre) tx_per_day_pre, sum(n_post)/sum(days_post) tx_per_day_post
FROM pp JOIN c USING(product_id)"""))

hdr("4b. tx de tarjeta después del vencimiento + vigencia")
print(q("""SELECT ptype, count(*) n, count(expires) n_exp,
  min(date_diff('month', opened, expires)) min_m, max(date_diff('month', opened, expires)) max_m,
  quantile_disc(date_diff('month', opened, expires), 0.5) med_m
FROM pr WHERE ptype LIKE 'Tarjeta%' GROUP BY 1"""))
print(q(f"""
SELECT p.ptype, count(*) n_tx_card, count(p.expires) n_tx_card_with_exp,
  avg(CASE WHEN p.expires IS NOT NULL THEN (t.ts::DATE > p.expires)::INT END) obs_after_exp_among_with_exp,
  sum(coalesce((t.ts::DATE > p.expires)::INT,0))*1.0/count(*) obs_after_exp_all_card_tx,
  avg(CASE WHEN p.expires IS NOT NULL THEN greatest(0, least(1, (epoch({W1}) - epoch(p.expires::TIMESTAMP)) / (epoch({W1}) - epoch({W0})))) END) exp_uniform
FROM tx t JOIN pr p USING(product_id) WHERE p.ptype LIKE 'Tarjeta%' GROUP BY ROLLUP(p.ptype) ORDER BY 1 NULLS LAST"""))

hdr("4c. tx antes del registro del cliente")
print(q(f"""
SELECT count(*) n_tx, avg((t.ts < c.registration_date)::INT) obs_before_reg,
  avg(greatest(0, least(1, (epoch(c.registration_date) - epoch({W0})) / (epoch({W1}) - epoch({W0}))))) exp_uniform,
  avg((t.customer_id = p.customer_id)::INT) tx_cust_eq_prod_cust
FROM tx t JOIN cu c ON c.customer_id=t.customer_id JOIN pr p ON p.product_id=t.product_id"""))
print(q(f"""
SELECT year(c.registration_date) y_reg, count(*) n_tx,
  round(100*avg((t.ts < c.registration_date)::INT),1) obs_pct,
  round(100*avg(greatest(0, least(1, (epoch(c.registration_date) - epoch({W0})) / (epoch({W1}) - epoch({W0}))))),1) exp_pct
FROM tx t JOIN cu c USING(customer_id) GROUP BY 1 ORDER BY 1"""))

hdr("5. Productos abiertos antes del registro del cliente")
print(q("""SELECT count(*) n_prod, avg((p.opened < c.registration_date::DATE)::INT) share_open_before_reg,
  avg((p.opened < c.registration_date::DATE - INTERVAL 365 DAY)::INT) share_open_before_reg_1y
FROM pr p JOIN cu c USING(customer_id)"""))

hdr("6. last_updated fuera de rango")
print(q("""SELECT max(last_updated) max_lu_all, count(*) n,
  avg((last_updated > TIMESTAMP '2026-06-18 06:00:00')::INT) share_lu_after_end,
  max(CASE WHEN last_tx IS NOT NULL THEN last_updated END) max_lu_lt_nonnull,
  avg(CASE WHEN last_tx IS NOT NULL THEN (last_tx <= last_updated)::INT END) lt_le_lu
FROM pr"""))

hdr("7. Rechazo / código 54 / fraude dentro vs fuera de la vigencia")
print(q("""
SELECT CASE WHEN t.ts::DATE < p.opened THEN '1_pre_apertura'
            WHEN p.expires IS NOT NULL AND t.ts::DATE > p.expires THEN '3_post_vencimiento'
            ELSE '2_dentro_vigencia' END grp,
  count(*) n, round(100*avg((t.status='Declined')::INT),2) decl_pct,
  round(100*avg((t.code='54')::INT),2) code54_pct,
  round(100*avg(CASE WHEN t.status='Declined' THEN (t.code='54')::INT END),2) code54_among_decl_pct,
  round(1000*avg(t.fraud::INT),3) fraud_per_mil, sum(t.fraud::INT) n_fraud
FROM tx t JOIN pr p USING(product_id) GROUP BY 1 ORDER BY 1"""))
# sólo tarjetas: dentro vs después del vencimiento
print(q("""
SELECT (t.ts::DATE > p.expires) post_exp, count(*) n,
  round(100*avg((t.status='Declined')::INT),2) decl_pct, round(100*avg((t.code='54')::INT),2) code54_pct,
  round(1000*avg(t.fraud::INT),3) fraud_per_mil
FROM tx t JOIN pr p USING(product_id) WHERE p.expires IS NOT NULL AND t.ts::DATE >= p.opened GROUP BY 1 ORDER BY 1"""))

hdr("8. Regla del generador (refinamiento): last_tx ~ U(opened, fin) y last_updated ~ opened + U(0, 1 año)?")
print(q("""
SELECT count(*) n,
  quantile_cont((epoch(last_tx) - epoch(opened::TIMESTAMP)) / (epoch(TIMESTAMP '2026-06-18 00:00:00') - epoch(opened::TIMESTAMP)), [0.01,0.1,0.25,0.5,0.75,0.9,0.99]) u_lasttx_q,
  avg((last_tx > TIMESTAMP '2026-06-18 00:00:00')::INT) lt_after_end
FROM pr WHERE last_tx IS NOT NULL AND opened < DATE '2026-06-10'"""))
print(q("""
SELECT count(*) n, min(date_diff('day', opened, last_updated::DATE)) min_d, max(date_diff('day', opened, last_updated::DATE)) max_d,
  quantile_cont(date_diff('day', opened, last_updated::DATE), [0.01,0.25,0.5,0.75,0.99]) q_d,
  corr(epoch(last_updated), epoch(opened::TIMESTAMP)) corr_lu_open
FROM pr"""))
