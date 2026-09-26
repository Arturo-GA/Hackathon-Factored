"""Pruebas de señal: ¿qué columnas sirven como etiquetas o evidencia para el reto?

Complementa a profile_tables.py. Para cada candidata a etiqueta mide si hay
relación real con otras variables (AUC, pureza de mapeos, tasas por grupo).
AUC ≈ 0.5 => sin señal (probable ruido del generador sintético).

Salida: docs/signal_checks.md
Uso:    python analysis/signal_checks.py
"""
import math
import os
import re

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

BRONZE_DIR = "data/bronze"
OUT_MD = "docs/signal_checks.md"
TARGET_SAMPLE = 500_000
out = []


def say(line=""):
    print(line, flush=True)
    out.append(line)


def read(table, columns=None, sample=False):
    pf = pq.ParquetFile(os.path.join(BRONZE_DIR, f"{table}.parquet"))
    if sample and pf.metadata.num_rows > 1_000_000:
        k = math.ceil(pf.metadata.num_rows / TARGET_SAMPLE)
        return pf.read_row_groups(list(range(0, pf.num_row_groups, k)), columns=columns).to_pandas()
    return pf.read(columns=columns).to_pandas()


def num(s):
    return pd.to_numeric(s, errors="coerce")


def auc(y, score):
    m = ~(pd.isna(y) | pd.isna(score))
    if m.sum() < 100 or pd.Series(y[m]).nunique() < 2:
        return float("nan")
    return round(roc_auc_score(y[m], score[m]), 3)


def model_auc(df, target, features, groups):
    """AUC en held-out (split por cliente) de un GBM con features categóricas y numéricas."""
    X = pd.DataFrame(index=df.index)
    for f in features:
        v = num(df[f])
        X[f] = v if v.notna().mean() > 0.9 else df[f].astype("category").cat.codes
    y = df[target].astype(int).values
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=0).split(X, y, groups))
    clf = HistGradientBoostingClassifier(max_iter=200, random_state=0).fit(X.iloc[tr], y[tr])
    return round(roc_auc_score(y[te], clf.predict_proba(X.iloc[te])[:, 1]), 3)


def rate_table(df, by, target, min_n=200):
    g = df.groupby(by, observed=True)[target].agg(["mean", "size"])
    g = g[g["size"] >= min_n].sort_values("mean", ascending=False)
    return ", ".join(f"{i}={100*r['mean']:.1f}% (n={int(r['size']):,})" for i, r in g.iterrows())


def purity(df, key, label):
    """% de filas cuyo label coincide con el label mayoritario de su key (1.0 = mapeo determinista)."""
    top = df.groupby(key)[label].agg(lambda s: s.value_counts().iloc[0]).sum()
    return round(top / len(df), 4)


def section(title):
    say()
    say(f"## {title}")
    say()


def main():
    say("# Pruebas de señal: LATAM Bank")
    say()
    say("Generado por `analysis/signal_checks.py`. AUC ≈ 0.5 = sin señal; 1.0 = determinista (posible fuga).")

    # ---------------------------------------------------------------- transcripts
    section("1. Transcripts → motivo de contacto (¿sirve para un clasificador de intención?)")
    tr = read("call_transcripts", ["interaction_id", "customer_id", "customer_text", "agent_text", "main_topics", "detected_intents"])
    cc = read("call_center_interactions")
    t = tr.merge(cc[["interaction_id", "reason_category"]], on="interaction_id", how="left")
    say(f"- Transcripts: {len(t):,} · textos de cliente únicos: {t['customer_text'].nunique()} · de agente: {t['agent_text'].nunique()}")
    say(f"- Pureza customer_text → reason_category: {purity(t, 'customer_text', 'reason_category'):.2%}")
    say(f"- main_topics == reason_category: {(t['main_topics'] == t['reason_category']).mean():.2%} (fuga si se usa como feature)")
    say(f"- detected_intents valores: {t['detected_intents'].value_counts(dropna=False).to_dict()}")
    # Los textos son una apertura fija + 0-2 frases de cierre combinadas al azar.
    t["apertura"] = t["customer_text"].str.split(".").str[0]
    closings = set()
    for txt in t["customer_text"].unique():
        closings.update(p.strip() for p in re.split(r"(?<=[.?])\s+", txt)[1:] if p.strip())
    say(f"- Aperturas distintas: {t['apertura'].nunique()} · frases de cierre distintas: {len(closings)}: {sorted(closings)}")
    say("- % de cada apertura dentro de cada categoría (si el texto no informa, todas ≈ iguales):")
    ct = pd.crosstab(t["reason_category"], t["apertura"], normalize="index").round(3) * 100
    for cat, row in ct.iterrows():
        say(f"  - {cat}: " + ", ".join(f"«{k}» {v:.1f}%" for k, v in row.items()))

    # ---------------------------------------------------------------- call center
    section("2. Call center: ¿qué explica resolver en el primer contacto (FCR) y escalar?")
    c = cc.copy()
    c["resolved"] = c["was_resolved"] == "True"
    c["escalated"] = c["was_escalated"] == "True"
    c["accent_match"] = np.where(c["customer_detected_accent"].isna(), "sin dato",
                                 np.where(c["customer_detected_accent"] == c["agent_used_accent"], "coincide", "distinto"))
    ag = read("service_agents", ["agent_id", "experience_level", "specialty", "languages"])
    c = c.merge(ag, on="agent_id", how="left")
    feats = ["reason_category", "channel", "interaction_type", "detected_sentiment", "sentiment_score",
             "duration_seconds", "wait_time_seconds", "accent_match", "experience_level", "specialty"]
    say(f"- FCR por categoría: {rate_table(c, 'reason_category', 'resolved')}")
    say(f"- FCR por canal: {rate_table(c, 'channel', 'resolved')}")
    say(f"- FCR por sentimiento: {rate_table(c, 'detected_sentiment', 'resolved')}")
    say(f"- FCR por acento cliente/agente: {rate_table(c, 'accent_match', 'resolved')}")
    say(f"- FCR por experiencia del agente: {rate_table(c, 'experience_level', 'resolved')}")
    say(f"- Escalado por sentimiento: {rate_table(c, 'detected_sentiment', 'escalated')}")
    say(f"- AUC modelo (held-out por cliente) → was_resolved: {model_auc(c, 'resolved', feats, c['customer_id'])}")
    say(f"- AUC modelo (held-out por cliente) → was_escalated: {model_auc(c, 'escalated', feats, c['customer_id'])}")

    # ---------------------------------------------------------------- surveys
    section("3. Encuestas: ¿la satisfacción responde a lo que pasó en la llamada?")
    sv = read("satisfaction_surveys", ["interaction_id", "survey_type", "main_score", "comment_sentiment"])
    s = sv.merge(c[["interaction_id", "resolved", "escalated", "reason_category", "wait_time_seconds"]], on="interaction_id", how="left")
    s["score"] = num(s["main_score"])
    for st, g in s.groupby("survey_type"):
        say(f"- {st}: rango {g['score'].min():g}–{g['score'].max():g}; media si resuelto={g.loc[g.resolved, 'score'].mean():.2f} vs no resuelto={g.loc[~g.resolved, 'score'].mean():.2f}")
    csat = s[s["survey_type"] == "CSAT"]
    say(f"- AUC wait_time_seconds → CSAT bajo (≤2): {auc((csat['score'] <= 2).astype(int).values, num(csat['wait_time_seconds']).values)}")

    # ---------------------------------------------------------------- complaints
    section("4. Reclamos (disputas): mapeos y señal para prioridad / SLA")
    cp = read("complaints")
    say(f"- description únicas: {cp['description'].nunique()} · pureza description → category: {purity(cp, 'description', 'category'):.2%}")
    say(f"- Pureza subcategory → category (sin nulos): {purity(cp.dropna(subset=['subcategory']), 'subcategory', 'category'):.2%}")
    say("- Cruce category × subcategory (conteos):")
    ct = pd.crosstab(cp["category"], cp["subcategory"].fillna("(nulo)"))
    for cat, row in ct.iterrows():
        say(f"  - {cat}: " + ", ".join(f"{k}={v:,}" for k, v in row.items() if v))
    cp["sla"] = cp["sla_breached"] == "True"
    cp["amount"] = num(cp["claimed_amount"])
    say(f"- SLA incumplido por prioridad: {rate_table(cp, 'priority', 'sla')}")
    say(f"- SLA incumplido por categoría: {rate_table(cp, 'category', 'sla')}")
    say(f"- SLA incumplido por canal: {rate_table(cp, 'reception_channel', 'sla')}")
    say(f"- Días de resolución (mediana) por prioridad: " + ", ".join(
        f"{k}={v:g}" for k, v in cp.assign(d=num(cp['resolution_days'])).groupby('priority')['d'].median().items()))
    cp["critical_high"] = cp["priority"].isin(["Critical", "High"])
    say(f"- AUC claimed_amount → prioridad alta/crítica: {auc(cp['critical_high'].astype(int).values, cp['amount'].values)}")
    say(f"- AUC modelo → sla_breached: {model_auc(cp, 'sla', ['case_type', 'category', 'subcategory', 'reception_channel', 'priority', 'claimed_amount', 'is_repeat_complainer'], cp['customer_id'])}")
    say(f"- AUC modelo → prioridad alta/crítica: {model_auc(cp, 'critical_high', ['case_type', 'category', 'subcategory', 'reception_channel', 'claimed_amount', 'is_repeat_complainer'], cp['customer_id'])}")
    say(f"- Estados: {cp['status'].value_counts().to_dict()}")

    # ---------------------------------------------------------------- transactions
    section("5. Transacciones: códigos de rechazo y fraude")
    tx = read("transactions", sample=True)
    say(f"- Muestra: {len(tx):,} filas")
    say("- Cruce transaction_status × response_code:")
    ct = pd.crosstab(tx["transaction_status"], tx["response_code"].fillna("(nulo)"))
    for st, row in ct.iterrows():
        say(f"  - {st}: " + ", ".join(f"{k}={v:,}" for k, v in row.items() if v))
    tx["fraud"] = tx["is_fraud"] == "True"
    say(f"- Fraudes en muestra: {int(tx['fraud'].sum()):,} ({tx['fraud'].mean():.3%})")
    say(f"- AUC fraud_score → is_fraud: {auc(tx['fraud'].astype(int).values, num(tx['fraud_score']).values)}")
    say(f"- AUC amount → is_fraud: {auc(tx['fraud'].astype(int).values, num(tx['amount']).values)}")
    say(f"- Fraude por canal: {rate_table(tx, 'channel', 'fraud', min_n=1000)}")
    say(f"- Fraude por país: {rate_table(tx, 'transaction_country', 'fraud', min_n=1000)}")
    say(f"- AUC modelo → is_fraud: {model_auc(tx, 'fraud', ['transaction_type', 'channel', 'amount', 'currency', 'transaction_country', 'merchant_category', 'transaction_status'], tx['customer_id'])}")
    say(f"- Monedas: {tx['currency'].value_counts().to_dict()} (¿MXN ausente?)")
    say(f"- Países: {tx['transaction_country'].value_counts().to_dict()}")

    # ---------------------------------------------------------------- credit
    section("6. Crédito: ¿la mora (days_past_due) tiene relación con el perfil del cliente?")
    pr = read("products")
    cu = read("customers")
    credit = pr[pr["product_type"].isin(["Tarjeta Crédito", "Préstamo Personal", "Préstamo Hipotecario"])].copy()
    say(f"- Productos de crédito: {len(credit):,} · tipos de producto: {pr['product_type'].value_counts().to_dict()}")
    say(f"- days_past_due no nulo en crédito: {credit['days_past_due'].notna().mean():.1%} · valores: {credit['days_past_due'].value_counts(dropna=False).to_dict()}")
    say(f"- ¿days_past_due en productos NO crédito?: {pr.loc[~pr.index.isin(credit.index), 'days_past_due'].notna().sum():,}")
    credit = credit.merge(cu[["customer_id", "credit_score", "estimated_monthly_income", "segment", "occupation", "customer_status", "date_of_birth"]], on="customer_id", how="left")
    credit["mora30"] = num(credit["days_past_due"]) >= 30
    m = credit["days_past_due"].notna()
    cr = credit[m]
    say(f"- Mora ≥30 días: {cr['mora30'].mean():.2%} de {len(cr):,} productos con dato")
    say(f"- AUC -credit_score → mora≥30: {auc(cr['mora30'].astype(int).values, -num(cr['credit_score']).values)}")
    say(f"- AUC -ingreso → mora≥30: {auc(cr['mora30'].astype(int).values, -num(cr['estimated_monthly_income']).values)}")
    say(f"- Mora por segmento: {rate_table(cr, 'segment', 'mora30')}")
    cr = cr.assign(edad=2026 - pd.to_datetime(cr["date_of_birth"], errors="coerce").dt.year)
    say(f"- AUC modelo → mora≥30: {model_auc(cr, 'mora30', ['credit_score', 'estimated_monthly_income', 'segment', 'occupation', 'product_type', 'current_balance', 'credit_limit', 'interest_rate', 'edad'], cr['customer_id'])}")
    say(f"- Monedas de productos: {pr['currency'].value_counts().to_dict()}")

    # ---------------------------------------------------------------- consistency
    section("7. Consistencia entre columnas")
    say(f"- document_type por país: " + "; ".join(
        f"{k}: {v}" for k, v in cu.groupby("country")["document_type"].agg(lambda s: s.value_counts().to_dict()).items()))
    say(f"- Ejemplos registration_branch_id: {cu['registration_branch_id'].head(3).tolist()} vs branch_id: {read('branches', ['branch_id'])['branch_id'].head(3).tolist()}")
    say(f"- Ejemplos assigned_branch_id agentes: {ag.merge(read('service_agents', ['agent_id', 'assigned_branch_id']), on='agent_id')['assigned_branch_id'].dropna().head(3).tolist()}")
    say(f"- customers.last_updated en el futuro (> 2026-06-17): {(pd.to_datetime(cu['last_updated'], errors='coerce') > '2026-06-18').mean():.1%}")
    say(f"- products.last_updated en el futuro: {(pd.to_datetime(pr['last_updated'], errors='coerce') > '2026-06-18').mean():.1%}")
    blocked = pr[pr["product_status"] == "Blocked"]
    say(f"- Productos bloqueados: {len(blocked):,} · por tipo: {blocked['product_type'].value_counts().to_dict()}")
    exp = pd.to_datetime(pr["expiration_date"], errors="coerce")
    say(f"- Productos vencidos (expiration < 2026-06-17) pero Active: {int(((exp < '2026-06-17') & (pr['product_status'] == 'Active')).sum()):,}")
    say(f"- Agentes que hablan portugués: {int(ag['languages'].str.contains('portugués').sum())} de {len(ag)} · especialidades: {ag['specialty'].value_counts(dropna=False).to_dict()}")

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"\nListo: {OUT_MD}")


if __name__ == "__main__":
    main()
