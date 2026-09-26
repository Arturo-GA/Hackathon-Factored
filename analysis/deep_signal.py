"""Segunda pasada de señal: cruces entre tablas completas con ventanas de tiempo.

Usa DuckDB sobre los Parquet de data/bronze (sin muestreo en los cruces).
Criterios:
  - Modelos: AUC en held-out agrupado por cliente con IC 95% bootstrap.
    Si el IC incluye 0.5 => sin señal.
  - Comparaciones de tasas: chi² + V de Cramér (efecto). Con millones de filas
    casi todo es "significativo"; V < 0.02 se considera efecto despreciable.

Salida: docs/deep_signal.md
Uso:    python analysis/deep_signal.py [--sections 1 3 6]
"""
import argparse
import json
import os

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

B = "data/bronze"
OUT_MD = "docs/deep_signal.md"
SNAPSHOT = "2026-06-17"
out = []
con = duckdb.connect()
con.execute("SET memory_limit='3GB'; SET threads=6; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")


def say(line=""):
    print(line, flush=True)
    out.append(line)


def q(sql):
    return con.execute(sql).df()


def views():
    con.execute(f"""
    CREATE OR REPLACE VIEW cc AS SELECT interaction_id, customer_id, agent_id,
      TRY_CAST(interaction_date AS TIMESTAMP) ts, reason_category cat, channel, interaction_type itype,
      was_resolved='True' resolved, was_escalated='True' escalated, requires_followup='True' followup,
      detected_sentiment sent, TRY_CAST(sentiment_score AS DOUBLE) sent_score,
      TRY_CAST(duration_seconds AS DOUBLE) dur, TRY_CAST(wait_time_seconds AS DOUBLE) wait,
      customer_detected_accent c_acc, agent_used_accent a_acc
    FROM '{B}/call_center_interactions.parquet';

    CREATE OR REPLACE VIEW tx AS SELECT transaction_id, customer_id, product_id,
      TRY_CAST(transaction_date AS TIMESTAMP) ts, transaction_type ttype, transaction_status status,
      response_code code, TRY_CAST(amount AS DOUBLE) amount, currency, channel,
      CASE WHEN transaction_country='Mexico' THEN 'México' ELSE transaction_country END country,
      is_fraud='True' fraud, TRY_CAST(fraud_score AS DOUBLE) fscore, merchant_category mcat
    FROM '{B}/transactions.parquet';

    CREATE OR REPLACE VIEW cu AS SELECT customer_id, country, segment, gender, occupation,
      TRY_CAST(credit_score AS DOUBLE) score, TRY_CAST(estimated_monthly_income AS DOUBLE) income,
      customer_status cstatus, date_diff('year', TRY_CAST(date_of_birth AS DATE), DATE '{SNAPSHOT}') age,
      accepts_marketing='True' mkt, date_diff('day', TRY_CAST(registration_date AS DATE), DATE '{SNAPSHOT}') tenure
    FROM '{B}/customers.parquet';

    CREATE OR REPLACE VIEW pr AS SELECT product_id, customer_id, product_type ptype, currency pcur,
      TRY_CAST(current_balance AS DOUBLE) bal, TRY_CAST(credit_limit AS DOUBLE) lim,
      TRY_CAST(interest_rate AS DOUBLE) rate, TRY_CAST(opening_date AS DATE) opened,
      TRY_CAST(expiration_date AS DATE) expires, product_status pstatus,
      TRY_CAST(days_past_due AS DOUBLE) dpd, TRY_CAST(last_transaction_date AS TIMESTAMP) last_tx,
      opening_channel, has_linked_app='True' app
    FROM '{B}/products.parquet';

    CREATE OR REPLACE VIEW cp AS SELECT complaint_id, customer_id, TRY_CAST(creation_date AS TIMESTAMP) ts,
      case_type, category, subcategory, reception_channel rchan, affected_product_id,
      TRY_CAST(claimed_amount AS DOUBLE) claimed, currency, priority, status,
      sla_breached='True' sla, TRY_CAST(resolution_days AS DOUBLE) rdays, is_repeat_complainer='True' repeat
    FROM '{B}/complaints.parquet';

    CREATE OR REPLACE VIEW sv AS SELECT interaction_id, agent_id, survey_type,
      TRY_CAST(main_score AS DOUBLE) score, open_comments, comment_sentiment
    FROM '{B}/satisfaction_surveys.parquet';

    CREATE OR REPLACE VIEW de AS SELECT customer_id, TRY_CAST(event_date AS TIMESTAMP) ts, event_type,
      action, page_title, app_version, platform, channel
    FROM '{B}/digital_events.parquet';

    CREATE OR REPLACE VIEW cs AS SELECT customer_id, campaign_id, TRY_CAST(send_date AS TIMESTAMP) ts,
      send_channel, was_delivered='True' delivered, was_opened='True' opened, had_conversion='True' conv
    FROM '{B}/campaign_sends.parquet';

    CREATE OR REPLACE VIEW mc AS SELECT campaign_id, campaign_objective objective, promoted_product,
      target_segment FROM '{B}/marketing_campaigns.parquet';

    CREATE OR REPLACE VIEW ag AS SELECT agent_id, experience_level, specialty, languages, agent_type,
      TRY_CAST(avg_csat AS DOUBLE) avg_csat FROM '{B}/service_agents.parquet';

    CREATE OR REPLACE VIEW tr AS SELECT interaction_id, customer_id, customer_text, agent_text,
      mentioned_entities, detected_keywords FROM '{B}/call_transcripts.parquet';
    """)


# ------------------------------------------------------------------ estadística
def cramers(ct):
    ct = ct.loc[ct.sum(axis=1) > 0, ct.sum(axis=0) > 0]
    chi2, p, _, _ = chi2_contingency(ct)
    n = ct.values.sum()
    v = np.sqrt(chi2 / (n * (min(ct.shape) - 1))) if min(ct.shape) > 1 else 0
    return p, v


def chi_line(df, a, b):
    p, v = cramers(pd.crosstab(df[a], df[b]))
    return f"chi² p={p:.2g}, V de Cramér={v:.3f}{' (despreciable)' if v < 0.02 else ''}"


def auc_ci(y, s, n_boot=200, seed=0):
    y, s = np.asarray(y), np.asarray(s)
    m = ~(pd.isna(s))
    y, s = y[m], s[m]
    if len(np.unique(y)) < 2:
        return float("nan"), float("nan"), float("nan")
    base = roc_auc_score(y, s)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        if len(np.unique(y[i])) == 2:
            boots.append(roc_auc_score(y[i], s[i]))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return base, lo, hi


def fmt_auc(a):
    base, lo, hi = a
    tag = "SIN señal" if lo <= 0.5 <= hi else ("señal débil" if base < 0.6 else "CON señal")
    return f"AUC {base:.3f} [IC95 {lo:.3f}–{hi:.3f}] → {tag}"


def gbm(df, target, feats, group, max_rows=300_000):
    df = df.dropna(subset=[target])
    if len(df) > max_rows:
        df = df.sample(max_rows, random_state=0)
    X = pd.DataFrame(index=df.index)
    for f in feats:
        col = df[f]
        if col.dtype == bool:
            X[f] = col.astype(float)
        elif pd.api.types.is_numeric_dtype(col):
            X[f] = col.astype(float)
        else:
            X[f] = col.astype("category").cat.codes.replace(-1, np.nan)
    y = df[target].astype(int).values
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=0).split(X, y, df[group]))
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, random_state=0).fit(X.iloc[tr], y[tr])
    p = clf.predict_proba(X.iloc[te])[:, 1]
    # Importancia univariada (AUC de cada feature sola en test) para explicar de dónde sale la señal.
    uni = {}
    for f in feats:
        v = X.iloc[te][f].values
        if np.isnan(v).all() or len(np.unique(v[~np.isnan(v)])) < 2:
            continue
        a = roc_auc_score(y[te][~np.isnan(v)], v[~np.isnan(v)])
        uni[f] = round(max(a, 1 - a), 3)
    top = sorted(uni.items(), key=lambda kv: -kv[1])[:4]
    return auc_ci(y[te], p), top, len(df), y.mean()


def gbm_line(df, target, feats, group, label):
    a, top, n, rate = gbm(df, target, feats, group)
    say(f"- **{label}** (n={n:,}, positivos {rate:.1%}): {fmt_auc(a)} · features más informativas: {top}")


def rate_line(df, by, target, min_n=300):
    g = df.groupby(by, observed=True)[target].agg(["mean", "size"])
    g = g[g["size"] >= min_n].sort_values("mean", ascending=False)
    return ", ".join(f"{i}={100*r['mean']:.2f}% (n={int(r['size']):,})" for i, r in g.iterrows())


def section(n, title):
    say()
    say(f"## {n}. {title}")
    say()


# ------------------------------------------------------------------ secciones
def s1_demand():
    section(1, "Patrones de demanda del call center (686k contactos, completos)")
    h = q("SELECT hour(ts) h, COUNT(*) n FROM cc GROUP BY 1 ORDER BY 1")
    h["pct"] = 100 * h["n"] / h["n"].sum()
    say("- Por hora (%): " + " ".join(f"{int(r.h)}h={r.pct:.1f}" for r in h.itertuples()))
    d = q("SELECT dayname(ts) d, dayofweek(ts) k, COUNT(*) n FROM cc GROUP BY 1,2 ORDER BY 2")
    say("- Por día de semana: " + ", ".join(f"{r.d}={r.n:,}" for r in d.itertuples()))
    m = q("SELECT month(ts) m, COUNT(*) n FROM cc GROUP BY 1 ORDER BY 1")
    say("- Por mes: " + ", ".join(f"{int(r.m)}={r.n:,}" for r in m.itertuples()))
    tq = q("SELECT strftime(date_trunc('quarter', ts), '%Y-Q') || quarter(ts) qq, COUNT(*) n FROM cc GROUP BY 1 ORDER BY 1")
    say("- Por trimestre: " + ", ".join(f"{r.qq}={r.n:,}" for r in tq.itertuples()))
    daily = q("SELECT CAST(ts AS DATE) d, COUNT(*) n FROM cc GROUP BY 1")["n"]
    say(f"- Volumen diario: media {daily.mean():.0f}, desv. {daily.std():.0f}, índice de dispersión var/media={daily.var()/daily.mean():.2f} (≈1 = puro azar Poisson)")
    df = q("""SELECT c.cat, hour(c.ts) h, dayname(c.ts) dow, month(c.ts) mes, c.channel, u.country, u.segment,
                     CASE WHEN u.age<30 THEN '<30' WHEN u.age<45 THEN '30-44' WHEN u.age<60 THEN '45-59' ELSE '60+' END edad
              FROM cc c JOIN cu u USING(customer_id)""")
    for col in ["h", "dow", "mes", "channel", "country", "segment", "edad"]:
        say(f"- Motivo × {col}: {chi_line(df, 'cat', col)}")
    say(f"- Motivo por segmento: " + "; ".join(
        f"{s}: " + ", ".join(f"{k} {v:.1%}" for k, v in g['cat'].value_counts(normalize=True).head(3).items())
        for s, g in df.groupby('segment')))
    per_cust = q("SELECT customer_id, COUNT(*) n FROM cc GROUP BY 1")["n"]
    say(f"- Contactos por cliente: media {per_cust.mean():.2f}, p90 {per_cust.quantile(.9):.0f}, máx {per_cust.max()} · clientes sin contacto: {150000-len(per_cust):,}")
    aht = q("SELECT cat, median(dur) dur, median(wait) wait, COUNT(*) n FROM cc GROUP BY 1 ORDER BY n DESC")
    say("- Duración/espera mediana (s) por motivo: " + ", ".join(f"{r.cat}={r.dur:.0f}/{r.wait:.0f}" for r in aht.itertuples()))


def s2_recontact():
    section(2, "Recontacto: ¿'no resuelto' implica que el cliente vuelve a llamar?")
    df = q("""WITH o AS (SELECT customer_id, ts, resolved, cat, followup,
                LEAD(ts) OVER (PARTITION BY customer_id ORDER BY ts) nxt,
                LEAD(cat) OVER (PARTITION BY customer_id ORDER BY ts) nxt_cat FROM cc)
              SELECT resolved, followup, cat,
                (nxt IS NOT NULL AND nxt <= ts + INTERVAL 7 DAY) re7,
                (nxt IS NOT NULL AND nxt <= ts + INTERVAL 30 DAY) re30,
                (nxt_cat = cat) same_cat, nxt IS NOT NULL has_next FROM o""")
    say(f"- Recontacto ≤7 días por resuelto: {rate_line(df, 'resolved', 're7')}")
    say(f"- Recontacto ≤30 días por resuelto: {rate_line(df, 'resolved', 're30')}")
    say(f"- Recontacto ≤7 días por requiere seguimiento: {rate_line(df, 'followup', 're7')}")
    nx = df[df["has_next"]]
    exp = (df["cat"].value_counts(normalize=True) ** 2).sum()
    say(f"- Siguiente contacto con el MISMO motivo: {nx['same_cat'].mean():.1%} (esperado si fuera azar: {exp:.1%})")
    say(f"- Resuelto × recontacto 7d: {chi_line(df, 'resolved', 're7')}")


def s3_drivers():
    section(3, "¿Qué dispara un contacto o un reclamo? (transacciones → call center / reclamos)")
    df = q("""WITH j AS (
        SELECT t.transaction_id, t.status, COALESCE(t.code,'(nulo)') code, t.fraud,
          MAX(CASE WHEN c.ts > t.ts AND c.ts <= t.ts + INTERVAL 7 DAY THEN 1 ELSE 0 END) post7,
          MAX(CASE WHEN c.ts <= t.ts AND c.ts > t.ts - INTERVAL 7 DAY THEN 1 ELSE 0 END) pre7,
          MAX(CASE WHEN c.cat='Transaccional' AND c.ts > t.ts AND c.ts <= t.ts + INTERVAL 7 DAY THEN 1 ELSE 0 END) post7_trx,
          MAX(CASE WHEN c.cat='Queja' AND c.ts > t.ts AND c.ts <= t.ts + INTERVAL 7 DAY THEN 1 ELSE 0 END) post7_queja
        FROM tx t LEFT JOIN cc c ON c.customer_id = t.customer_id
          AND c.ts > t.ts - INTERVAL 7 DAY AND c.ts <= t.ts + INTERVAL 7 DAY
        GROUP BY 1,2,3,4)
      SELECT status, code, fraud, COUNT(*) n, AVG(post7) post7, AVG(pre7) pre7, AVG(post7_trx) post7_trx, AVG(post7_queja) post7_queja
      FROM j GROUP BY 1,2,3""")
    def agg(by):
        g = df.groupby(by).apply(lambda x: pd.Series({
            "n": x["n"].sum(),
            "post7": np.average(x["post7"], weights=x["n"]), "pre7": np.average(x["pre7"], weights=x["n"]),
            "trx": np.average(x["post7_trx"], weights=x["n"]), "queja": np.average(x["post7_queja"], weights=x["n"])}),
            include_groups=False)
        return "; ".join(f"{i}: contacto 7d después {r.post7:.2%} vs antes {r.pre7:.2%}, Transaccional {r.trx:.2%}, Queja {r.queja:.2%} (n={int(r.n):,})" for i, r in g.iterrows())
    say(f"- Por estado: {agg('status')}")
    say(f"- Por código: {agg('code')}")
    say(f"- Por fraude: {agg('fraud')}")
    comp = q("""WITH j AS (
        SELECT t.transaction_id, t.status, t.fraud,
          MAX(CASE WHEN p.ts IS NOT NULL THEN 1 ELSE 0 END) any30,
          MAX(CASE WHEN p.category='Transactions' THEN 1 ELSE 0 END) trx30
        FROM tx t LEFT JOIN cp p ON p.customer_id=t.customer_id AND p.ts > t.ts AND p.ts <= t.ts + INTERVAL 30 DAY
        GROUP BY 1,2,3)
      SELECT status, fraud, COUNT(*) n, AVG(any30) any30, AVG(trx30) trx30 FROM j GROUP BY 1,2 ORDER BY 1,2""")
    say("- Reclamo en los 30 días siguientes a la transacción: " + "; ".join(
        f"{r.status}/fraude={r.fraud}: cualquiera {r.any30:.2%}, categoría Transactions {r.trx30:.2%} (n={r.n:,})" for r in comp.itertuples()))
    blk = q("""SELECT p.pstatus, COUNT(DISTINCT p.customer_id) clientes,
                 AVG(CASE WHEN c.n IS NULL THEN 0 ELSE c.n END) contactos_prom
               FROM pr p LEFT JOIN (SELECT customer_id, COUNT(*) n FROM cc GROUP BY 1) c USING(customer_id)
               GROUP BY 1 ORDER BY 1""")
    say("- Contactos promedio del cliente según estado de su producto: " + ", ".join(f"{r.pstatus}={r.contactos_prom:.2f}" for r in blk.itertuples()))


def s4_disputes():
    section(4, "Disputas: ¿los reclamos se pueden anclar a transacciones reales?")
    df = q("""WITH c AS (SELECT * FROM cp WHERE affected_product_id IS NOT NULL),
      m AS (SELECT c.complaint_id,
          MAX(CASE WHEN t.ts BETWEEN c.ts - INTERVAL 30 DAY AND c.ts THEN 1 ELSE 0 END) tx30,
          MAX(CASE WHEN c.claimed IS NOT NULL AND abs(t.amount - c.claimed) <= 0.01*c.claimed THEN 1 ELSE 0 END) amt_match,
          MAX(CASE WHEN t.fraud THEN 1 ELSE 0 END) fraud90,
          MAX(CASE WHEN t.status IN ('Reversed','Declined') THEN 1 ELSE 0 END) bad90
        FROM c LEFT JOIN tx t ON t.product_id = c.affected_product_id AND t.ts BETWEEN c.ts - INTERVAL 90 DAY AND c.ts
        GROUP BY 1)
      SELECT c.category, c.subcategory, c.claimed IS NOT NULL has_claim, p.ptype,
             (p.customer_id = c.customer_id) own_product, m.tx30, m.amt_match, m.fraud90, m.bad90
      FROM c JOIN m USING(complaint_id) LEFT JOIN pr p ON p.product_id = c.affected_product_id""")
    say(f"- Reclamos con producto afectado: {len(df):,}")
    say(f"- El producto afectado pertenece al mismo cliente: {df['own_product'].mean():.1%}")
    for col, lab in [("tx30", "tiene transacciones en ese producto en los 30 días previos"),
                     ("fraud90", "tiene una transacción marcada fraude en 90 días previos"),
                     ("bad90", "tiene una transacción rechazada/revertida en 90 días previos")]:
        say(f"- % que {lab}, por categoría: {rate_line(df, 'category', col)}")
    hc = df[df["has_claim"]]
    say(f"- Monto reclamado coincide (±1%) con alguna transacción del producto en 90 días: {rate_line(hc, 'category', 'amt_match')}")
    say(f"- Tipo de producto afectado × categoría del reclamo: {chi_line(df.dropna(subset=['ptype']), 'category', 'ptype')}")
    say("- Top tipo de producto por categoría: " + "; ".join(
        f"{k}: " + ", ".join(f"{a} {b:.0%}" for a, b in g['ptype'].value_counts(normalize=True).head(3).items())
        for k, g in df.groupby('category')))


def s5_codes():
    section(5, "Códigos de rechazo vs estado real del producto (¿explicaciones consistentes?)")
    df = q("""SELECT t.status, COALESCE(t.code,'(nulo)') code, COUNT(*) n,
        AVG(CASE WHEN p.expires IS NOT NULL AND p.expires < CAST(t.ts AS DATE) THEN 1 ELSE 0 END) expirado,
        AVG(CASE WHEN p.pstatus IN ('Blocked','Closed','Suspended') THEN 1 ELSE 0 END) prod_inactivo,
        AVG(CASE WHEN t.amount > p.bal THEN 1 ELSE 0 END) monto_mayor_saldo,
        AVG(CASE WHEN t.currency <> p.pcur THEN 1 ELSE 0 END) moneda_distinta
      FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2 ORDER BY 1,2""")
    say("| Estado | Código | n | Producto vencido | Producto bloqueado/cerrado | Monto > saldo | Moneda ≠ producto |")
    say("|---|---|---|---|---|---|---|")
    for r in df.itertuples():
        say(f"| {r.status} | {r.code} | {r.n:,} | {r.expirado:.1%} | {r.prod_inactivo:.1%} | {r.monto_mayor_saldo:.1%} | {r.moneda_distinta:.1%} |")
    combo = q("""SELECT p.ptype, t.ttype, COUNT(*) n FROM tx t JOIN pr p USING(product_id) GROUP BY 1,2""")
    ct = combo.pivot(index="ptype", columns="ttype", values="n").fillna(0)
    say(f"- Tipo de producto × tipo de transacción: {cramers(ct)[1]:.3f} V de Cramér (0 = cualquier producto hace cualquier cosa)")
    say("- Ejemplos raros: " + ", ".join(f"{r.ttype} en {r.ptype}={r.n:,}" for r in combo[
        combo["ptype"].isin(["Préstamo Hipotecario", "Seguro", "Inversión"]) & combo["ttype"].isin(["Purchase", "Withdrawal"])].itertuples()))
    cc = q("""SELECT u.country cliente, t.country tx, COUNT(*) n FROM tx t JOIN cu u USING(customer_id) GROUP BY 1,2""")
    same = cc[cc["cliente"] == cc["tx"]]["n"].sum() / cc["n"].sum()
    say(f"- Transacciones en el mismo país del cliente: {same:.1%}")


def s6_credit():
    section(6, "Crédito (segunda pasada): mora con features cruzadas de 6 tablas")
    df = q(f"""WITH t AS (
        SELECT product_id, COUNT(*) n_tx, SUM(amount) sum_amt,
          SUM(CASE WHEN status='Declined' THEN 1 ELSE 0 END) n_decl,
          SUM(CASE WHEN code='51' THEN 1 ELSE 0 END) n_51,
          SUM(CASE WHEN ttype='Payment' THEN 1 ELSE 0 END) n_pay,
          SUM(CASE WHEN status='Reversed' THEN 1 ELSE 0 END) n_rev,
          date_diff('day', MAX(ts), TIMESTAMP '{SNAPSHOT}') dias_sin_tx
        FROM tx WHERE ts >= TIMESTAMP '{SNAPSHOT}' - INTERVAL 180 DAY GROUP BY 1),
      c AS (SELECT customer_id, COUNT(*) n_cc, SUM(CASE WHEN cat='Queja' THEN 1 ELSE 0 END) n_queja,
              AVG(CASE WHEN resolved THEN 1 ELSE 0 END) fcr FROM cc GROUP BY 1),
      k AS (SELECT customer_id, COUNT(*) n_cp, SUM(CASE WHEN category='Fees' THEN 1 ELSE 0 END) n_fees FROM cp GROUP BY 1),
      d AS (SELECT customer_id, COUNT(*) n_dig FROM de WHERE customer_id IS NOT NULL GROUP BY 1),
      np AS (SELECT customer_id, COUNT(*) n_prod, SUM(CASE WHEN pstatus<>'Active' THEN 1 ELSE 0 END) n_inact FROM pr GROUP BY 1)
      SELECT p.product_id, p.customer_id, p.ptype, p.dpd, p.bal, p.lim, p.bal/NULLIF(p.lim,0) util, p.rate, p.pstatus,
        date_diff('day', p.opened, DATE '{SNAPSHOT}') antig, p.opening_channel, p.app,
        u.score, u.income, u.segment, u.age, u.country, u.occupation, u.cstatus, u.tenure,
        t.n_tx, t.sum_amt, t.n_decl, t.n_51, t.n_pay, t.n_rev, t.dias_sin_tx,
        c.n_cc, c.n_queja, c.fcr, k.n_cp, k.n_fees, d.n_dig, np.n_prod, np.n_inact
      FROM pr p JOIN cu u USING(customer_id)
      LEFT JOIN t USING(product_id) LEFT JOIN c USING(customer_id) LEFT JOIN k USING(customer_id)
      LEFT JOIN d USING(customer_id) LEFT JOIN np USING(customer_id)
      WHERE p.dpd IS NOT NULL""")
    df["mora30"] = df["dpd"] >= 30
    df["mora_any"] = df["dpd"] > 0
    feats = ["ptype", "bal", "lim", "util", "rate", "pstatus", "antig", "opening_channel", "app", "score", "income",
             "segment", "age", "country", "occupation", "cstatus", "tenure", "n_tx", "sum_amt", "n_decl", "n_51",
             "n_pay", "n_rev", "dias_sin_tx", "n_cc", "n_queja", "fcr", "n_cp", "n_fees", "n_dig", "n_prod", "n_inact"]
    gbm_line(df, "mora30", feats, "customer_id", "Mora ≥30 días")
    gbm_line(df, "mora_any", feats, "customer_id", "Cualquier mora (>0 días)")
    say(f"- Mora≥30 por estado del producto: {rate_line(df, 'pstatus', 'mora30')}")
    say(f"- Mora≥30 por tipo: {rate_line(df, 'ptype', 'mora30')}")


def s7_fraud():
    section(7, "Fraude (segunda pasada): features de comportamiento y cruce con cliente/producto")
    df = q(f"""WITH base AS (
        SELECT t.*, COUNT(*) OVER w24 vel24,
          t.amount / NULLIF(median(t.amount) OVER (PARTITION BY t.customer_id), 0) amt_ratio
        FROM tx t WINDOW w24 AS (PARTITION BY t.customer_id ORDER BY t.ts RANGE BETWEEN INTERVAL 1 DAY PRECEDING AND CURRENT ROW))
      SELECT b.customer_id, b.fraud, b.fscore, b.amount, b.amt_ratio, b.vel24, hour(b.ts) hora, dayofweek(b.ts) dow,
        b.ttype, b.channel, b.mcat, b.status, b.currency, (b.country <> u.country) pais_distinto,
        (b.currency <> p.pcur) moneda_distinta, p.ptype, p.pstatus, u.age, u.segment, u.score
      FROM base b JOIN cu u USING(customer_id) JOIN pr p USING(product_id)
      WHERE b.fraud OR hash(b.transaction_id) % 12 = 0""")
    say(f"- Filas: {len(df):,} (todos los fraudes + ~8% de legítimas) · fraudes: {int(df['fraud'].sum()):,}")
    say(f"- fraud_score solo: {fmt_auc(auc_ci(df['fraud'].astype(int), df['fscore']))}")
    feats = ["amount", "amt_ratio", "vel24", "hora", "dow", "ttype", "channel", "mcat", "status", "currency",
             "pais_distinto", "moneda_distinta", "ptype", "pstatus", "age", "segment", "score"]
    gbm_line(df, "fraud", feats, "customer_id", "Modelo SIN fraud_score")
    gbm_line(df, "fraud", feats + ["fscore"], "customer_id", "Modelo CON fraud_score")
    say(f"- Fraude por país distinto al del cliente: {rate_line(df, 'pais_distinto', 'fraud')}")
    s = df.dropna(subset=["fscore"])
    for thr in [50, 70, 80, 90]:
        sel = s["fscore"] >= thr
        say(f"- fraud_score ≥ {thr}: marca {sel.mean():.2%} de transacciones, precisión {s.loc[sel,'fraud'].mean():.2%}, recall {s.loc[sel,'fraud'].sum()/s['fraud'].sum():.1%}")


def s8_surveys_agents():
    section(8, "Encuestas y agentes: ¿hay efecto real del agente?")
    df = q("""SELECT c.interaction_id, c.agent_id, c.cat, c.resolved, c.wait, c.dur, s.survey_type, s.score,
                s.open_comments, s.comment_sentiment, a.experience_level, a.specialty, a.avg_csat
              FROM cc c LEFT JOIN sv s ON s.interaction_id = c.interaction_id LEFT JOIN ag a ON a.agent_id = c.agent_id""")
    sv = df.dropna(subset=["score"]).copy()
    sv["wait_q"] = pd.qcut(sv["wait"], 4, labels=False, duplicates="drop")
    com = sv.dropna(subset=["open_comments"])
    say(f"- Comentario × cuartil de espera: {chi_line(com.dropna(subset=['wait_q']), 'open_comments', 'wait_q')}")
    say(f"- Comentario × resuelto: {chi_line(com, 'open_comments', 'resolved')}")
    say(f"- Sentimiento del comentario × resuelto: {chi_line(com, 'comment_sentiment', 'resolved')}")
    for t in ["CSAT", "NPS", "CES"]:
        g = sv[sv["survey_type"] == t]
        say(f"- {t}: puntaje por resuelto (medias) " + ", ".join(f"{k}={v:.2f}" for k, v in g.groupby('resolved')['score'].mean().items())
            + f" · distribución: {g['score'].value_counts().sort_index().to_dict()}")
    agent = df.groupby("agent_id").agg(n=("resolved", "size"), fcr=("resolved", "mean")).query("n >= 300")
    p = df["resolved"].mean()
    ratio = agent["fcr"].var() / (p * (1 - p) / agent["n"]).mean()
    say(f"- FCR por agente ({len(agent)} agentes con ≥300 contactos): rango {agent['fcr'].min():.1%}–{agent['fcr'].max():.1%}; "
        f"varianza observada / esperada por azar = {ratio:.2f} (≈1 = no hay efecto agente)")
    csat = sv[sv["survey_type"] == "CSAT"].groupby("agent_id").agg(obs=("score", "mean"), n=("score", "size"), dec=("avg_csat", "first")).query("n >= 50").dropna()
    rho, pv = spearmanr(csat["obs"], csat["dec"])
    say(f"- avg_csat declarado del agente vs CSAT observado: Spearman ρ={rho:.3f} (p={pv:.2g}, {len(csat)} agentes)")
    sp = df.dropna(subset=["specialty"])
    say(f"- Especialidad del agente × motivo atendido: {chi_line(sp, 'specialty', 'cat')} (si hubiera enrutamiento por especialidad, V sería alto)")
    say(f"- FCR por especialidad: {rate_line(sp, 'specialty', 'resolved')}")


def s9_transcripts():
    section(9, "Transcripts (segunda pasada): texto del agente, entidades y coherencia con productos")
    df = q("""SELECT t.*, c.cat,
                EXISTS(SELECT 1 FROM pr p WHERE p.customer_id=t.customer_id AND p.ptype='Tarjeta Crédito') tiene_tc,
                EXISTS(SELECT 1 FROM pr p WHERE p.customer_id=t.customer_id AND p.ptype='Cuenta Ahorro') tiene_ahorro
              FROM tr t JOIN cc c USING(interaction_id)""")
    for col in ["agent_text", "detected_keywords", "mentioned_entities"]:
        top = df.groupby(col)["cat"].agg(lambda s: s.value_counts().iloc[0]).sum() / df[col].notna().sum()
        say(f"- Pureza {col} → motivo: {top:.1%} (azar ≈ {df['cat'].value_counts(normalize=True).iloc[0]:.1%}) · valores únicos: {df[col].nunique()}")
    def keys(s):
        try:
            v = json.loads(s)
            return tuple(sorted(v.keys())) if isinstance(v, dict) else (type(v).__name__,)
        except ValueError:
            return ("(no json)",)
    ents = df["mentioned_entities"].dropna().head(20000).map(keys)
    say(f"- Claves en mentioned_entities: {ents.value_counts().head(5).to_dict()}")
    say(f"- Ejemplo de mentioned_entities: {df['mentioned_entities'].dropna().iloc[0]}")
    say(f"- Ejemplo de agent_text: {df['agent_text'].iloc[0]}")
    df["pide_tc"] = df["customer_text"].str.contains("tarjeta de crédito")
    say(f"- Cliente que pregunta por tarjeta de crédito y SÍ tiene una: {df.loc[df.pide_tc,'tiene_tc'].mean():.1%} vs quien pregunta por ahorros: {df.loc[~df.pide_tc,'tiene_tc'].mean():.1%}")
    say(f"- Cliente que pregunta por ahorros y SÍ tiene cuenta de ahorro: {df.loc[~df.pide_tc,'tiene_ahorro'].mean():.1%} vs quien pregunta por TC: {df.loc[df.pide_tc,'tiene_ahorro'].mean():.1%}")


def s10_churn():
    section(10, "Fuga de clientes (customer_status ≠ Active) con historial de 5 tablas")
    df = q("""WITH c AS (SELECT customer_id, COUNT(*) n_cc, SUM(CASE WHEN cat='Retención' THEN 1 ELSE 0 END) n_ret,
                 SUM(CASE WHEN cat='Queja' THEN 1 ELSE 0 END) n_queja, AVG(CASE WHEN resolved THEN 1 ELSE 0 END) fcr,
                 AVG(sent_score) sent FROM cc GROUP BY 1),
           s AS (SELECT c.customer_id, AVG(s.score) sv_score FROM sv s JOIN cc c USING(interaction_id) GROUP BY 1),
           k AS (SELECT customer_id, COUNT(*) n_cp, AVG(CASE WHEN sla THEN 1 ELSE 0 END) sla FROM cp GROUP BY 1),
           t AS (SELECT customer_id, COUNT(*) n_tx, SUM(CASE WHEN status='Declined' THEN 1 ELSE 0 END) n_decl,
                 SUM(CASE WHEN fraud THEN 1 ELSE 0 END) n_fraud FROM tx GROUP BY 1),
           d AS (SELECT customer_id, COUNT(*) n_dig, SUM(CASE WHEN event_type='Error' THEN 1 ELSE 0 END) n_err FROM de WHERE customer_id IS NOT NULL GROUP BY 1),
           p AS (SELECT customer_id, COUNT(*) n_prod, SUM(CASE WHEN pstatus='Blocked' THEN 1 ELSE 0 END) n_blk FROM pr GROUP BY 1)
      SELECT u.*, c.n_cc, c.n_ret, c.n_queja, c.fcr, c.sent, s.sv_score, k.n_cp, k.sla, t.n_tx, t.n_decl, t.n_fraud,
             d.n_dig, d.n_err, p.n_prod, p.n_blk
      FROM cu u LEFT JOIN c USING(customer_id) LEFT JOIN s USING(customer_id) LEFT JOIN k USING(customer_id)
      LEFT JOIN t USING(customer_id) LEFT JOIN d USING(customer_id) LEFT JOIN p USING(customer_id)""")
    df["churn"] = df["cstatus"].isin(["Inactive", "Closed"])
    feats = ["country", "segment", "gender", "occupation", "score", "income", "age", "mkt", "tenure", "n_cc", "n_ret",
             "n_queja", "fcr", "sent", "sv_score", "n_cp", "sla", "n_tx", "n_decl", "n_fraud", "n_dig", "n_err", "n_prod", "n_blk"]
    gbm_line(df, "churn", feats, "customer_id", "Cliente Inactive/Closed")
    say(f"- Tasa de fuga según contactos de Retención (0 vs ≥1): {rate_line(df.assign(ret=df['n_ret'].fillna(0) > 0), 'ret', 'churn')}")
    say(f"- Clientes Closed/Inactive con transacciones: {(df.loc[df.churn, 'n_tx'].fillna(0) > 0).mean():.1%} (inconsistencia si es alto)")


def s11_campaigns():
    section(11, "Campañas: conversión y cumplimiento de consentimiento")
    df = q("""SELECT s.customer_id, s.conv, s.opened, s.send_channel, m.objective, m.promoted_product, m.target_segment,
                u.segment, u.age, u.country, u.mkt, u.score, u.income,
                EXISTS(SELECT 1 FROM pr p WHERE p.customer_id=s.customer_id AND p.ptype=m.promoted_product) ya_tiene
              FROM cs s JOIN mc m USING(campaign_id) JOIN cu u USING(customer_id)
              WHERE s.delivered AND hash(s.customer_id || s.campaign_id) % 4 = 0""")
    say(f"- Envíos entregados (muestra 25%): {len(df):,} · a clientes que NO aceptan marketing: {(~df['mkt']).mean():.1%}")
    say(f"- Envío a segmento distinto del objetivo de la campaña: {(df['target_segment'].notna() & (df['target_segment'] != df['segment'])).mean():.1%}")
    say(f"- Conversión si ya tiene el producto promovido: {rate_line(df, 'ya_tiene', 'conv')}")
    gbm_line(df, "conv", ["send_channel", "objective", "promoted_product", "segment", "age", "country", "mkt", "score", "income", "ya_tiene"],
             "customer_id", "Conversión")


def s12_digital():
    section(12, "Canal digital: errores por versión/plataforma y cruce con reclamos 'Problema con app'")
    df = q("""SELECT app_version, platform, channel, COUNT(*) n, AVG(CASE WHEN event_type='Error' THEN 1 ELSE 0 END) err
              FROM de GROUP BY 1,2,3""")
    for col in ["platform", "channel"]:
        g = df.groupby(col).apply(lambda x: np.average(x["err"], weights=x["n"]), include_groups=False)
        say(f"- Tasa de error por {col}: " + ", ".join(f"{k}={v:.2%}" for k, v in g.items()))
    v = df.dropna(subset=["app_version"]).groupby("app_version").apply(
        lambda x: pd.Series({"n": x["n"].sum(), "err": np.average(x["err"], weights=x["n"])}), include_groups=False)
    v = v[v["n"] >= 5000]
    p = np.average(v["err"], weights=v["n"])
    ratio = v["err"].var() / (p * (1 - p) / v["n"]).mean()
    say(f"- Error por app_version ({len(v)} versiones): rango {v['err'].min():.2%}–{v['err'].max():.2%}; varianza obs/esperada={ratio:.2f} (≈1 = ninguna versión es peor)")
    cmp_ = q("""WITH e AS (SELECT customer_id, ts FROM de WHERE event_type='Error' AND customer_id IS NOT NULL)
      SELECT c.subcategory, COUNT(*) n,
        AVG(CASE WHEN EXISTS(SELECT 1 FROM e WHERE e.customer_id=c.customer_id AND e.ts BETWEEN c.ts - INTERVAL 7 DAY AND c.ts) THEN 1 ELSE 0 END) err7
      FROM cp c GROUP BY 1 ORDER BY 1""")
    say("- Reclamo con error digital del cliente en los 7 días previos, por subcategoría: " + ", ".join(
        f"{r.subcategory}={r.err7:.2%} (n={r.n:,})" for r in cmp_.itertuples()))


SECTIONS = {1: s1_demand, 2: s2_recontact, 3: s3_drivers, 4: s4_disputes, 5: s5_codes, 6: s6_credit,
            7: s7_fraud, 8: s8_surveys_agents, 9: s9_transcripts, 10: s10_churn, 11: s11_campaigns, 12: s12_digital}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sections", nargs="*", type=int, default=list(SECTIONS))
    args = ap.parse_args()
    os.makedirs("data/duckdb_tmp", exist_ok=True)
    views()
    say("# Segunda pasada de señal: cruces entre tablas (LATAM Bank)")
    say()
    say("Generado por `analysis/deep_signal.py` con DuckDB sobre tablas completas. "
        "AUC con IC 95% bootstrap en held-out por cliente; V de Cramér < 0.02 = efecto despreciable.")
    for s in args.sections:
        try:
            SECTIONS[s]()
        except Exception as e:  # una sección rota no debe perder las demás
            say(f"- ⚠ Sección {s} falló: {type(e).__name__}: {e}")
    suffix = "" if args.sections == list(SECTIONS) else "_" + "_".join(map(str, args.sections))
    path = OUT_MD.replace(".md", f"{suffix}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"\nListo: {path}")


if __name__ == "__main__":
    main()
