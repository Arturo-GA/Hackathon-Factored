"""Perfil de calidad y contenido de las tablas bronze (Parquet local en data/bronze).

Tablas de hasta 1M de filas se leen completas. Las más grandes se muestrean por
días completos repartidos uniformemente en el tiempo (1 de cada k particiones),
para conservar la estacionalidad. Nota: con muestreo, los duplicados que caen en
días distintos (p. ej. llegadas tardías) pueden quedar subestimados.

Salida: docs/data_profile.md (legible) y docs/data_profile.json (máquina).

Uso:
  python analysis/profile_tables.py
  python analysis/profile_tables.py --tables complaints customers
"""
import argparse
import json
import math
import os
import re

import pandas as pd
import pyarrow.parquet as pq

BRONZE_DIR = "data/bronze"
OUT_MD = "docs/data_profile.md"
OUT_JSON = "docs/data_profile.json"
MAX_FULL_ROWS = 1_000_000
TARGET_SAMPLE = 500_000
LINEAGE = {"_source_file", "_process_date", "_ingested_at"}
NULL_LIKE = {"null", "none", "nan", "n/a", "na", "-", "?", "unknown", "desconocido", "sin dato", "sin datos"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

PRIMARY_KEYS = {
    "customers": "customer_id", "products": "product_id", "branches": "branch_id",
    "service_agents": "agent_id", "marketing_campaigns": "campaign_id",
    "transactions": "transaction_id", "call_center_interactions": "interaction_id",
    "call_transcripts": "transcript_id", "satisfaction_surveys": "survey_id",
    "digital_events": "event_id", "complaints": "complaint_id", "campaign_sends": "send_id",
}
# Columna con la fecha del evento, para medir llegadas tardías contra process_date.
EVENT_DATE = {
    "transactions": "transaction_date", "call_center_interactions": "interaction_date",
    "satisfaction_surveys": "survey_date", "digital_events": "event_date",
    "complaints": "creation_date", "campaign_sends": "send_date",
}
# Columna FK -> (tabla referenciada, PK referenciada)
FOREIGN_KEYS = {
    "customer_id": ("customers", "customer_id"),
    "product_id": ("products", "product_id"),
    "affected_product_id": ("products", "product_id"),
    "agent_id": ("service_agents", "agent_id"),
    "assigned_agent_id": ("service_agents", "agent_id"),
    "branch_id": ("branches", "branch_id"),
    "registration_branch_id": ("branches", "branch_id"),
    "opening_branch_id": ("branches", "branch_id"),
    "assigned_branch_id": ("branches", "branch_id"),
    "related_branch_id": ("branches", "branch_id"),
    "interaction_id": ("call_center_interactions", "interaction_id"),
    "origin_interaction_id": ("call_center_interactions", "interaction_id"),
    "campaign_id": ("marketing_campaigns", "campaign_id"),
}


def parquet_path(table):
    return os.path.join(BRONZE_DIR, f"{table}.parquet")


def load(table):
    pf = pq.ParquetFile(parquet_path(table))
    n = pf.metadata.num_rows
    if n <= MAX_FULL_ROWS:
        return pf.read().to_pandas(), n, "completa"
    k = math.ceil(n / TARGET_SAMPLE)
    groups = list(range(0, pf.num_row_groups, k))
    df = pf.read_row_groups(groups).to_pandas()
    return df, n, f"muestra de {len(df):,} filas (1 de cada {k} días, {len(groups)} días)"


def pct(x, total):
    return round(100 * x / total, 2) if total else 0.0


# Columnas con valores individuales (IDs y datos personales): nunca se listan sus valores frecuentes,
# para que el reporte pueda publicarse sin exponer registros del dataset.
SENSITIVE = {"first_name", "last_name", "email", "mobile_phone", "landline_phone", "phone", "address",
             "document_number", "ip_address", "product_number", "employee_code", "mentioned_products",
             "template_used", "campaign_name"}


def is_sensitive(name):
    return name in SENSITIVE or name.endswith("_id") or name.endswith("_ids")


def profile_column(s, name=""):
    info = _profile_column(s)
    if is_sensitive(name):
        info.pop("top", None)
    return info


def _profile_column(s):
    n = len(s)
    nn = s.dropna()
    info = {"null_pct": pct(n - len(nn), n), "distinct": int(nn.nunique())}
    if nn.empty:
        info["kind"] = "vacía"
        return info

    null_like = int(nn.str.strip().str.lower().isin(NULL_LIKE).sum())
    if null_like:
        info["null_like"] = null_like
    padded = int((nn != nn.str.strip()).sum())
    if padded:
        info["espacios_extremos"] = padded

    sample = nn.sample(200_000, random_state=0) if len(nn) > 200_000 else nn
    if nn.isin(["True", "False"]).all():
        info["kind"] = "booleano"
        info["pct_true"] = pct(int((nn == "True").sum()), len(nn))
        return info

    num = pd.to_numeric(sample, errors="coerce")
    if num.notna().mean() >= 0.98:
        full = pd.to_numeric(nn, errors="coerce")
        info["kind"] = "numérico"
        info["no_numericos"] = int(full.isna().sum())
        d = full.describe()
        info.update({"min": float(d["min"]), "p50": float(full.median()), "max": float(d["max"]), "media": float(d["mean"])})
        if info["distinct"] <= 12:
            info["top"] = top_values(nn)
        return info

    if sample.str.match(DATE_RE).mean() >= 0.98:
        dates = pd.to_datetime(nn, errors="coerce", format="ISO8601")
        info["kind"] = "fecha"
        info["no_parseables"] = int(dates.isna().sum())
        info["min"], info["max"] = str(dates.min()), str(dates.max())
        return info

    avg_len = float(sample.str.len().mean())
    if avg_len > 60:
        info["kind"] = "texto"
        info["largo_promedio"] = round(avg_len, 1)
    elif info["distinct"] / len(nn) > 0.9:
        info["kind"] = "id"
    else:
        info["kind"] = "categórica"
        info["top"] = top_values(nn)
    return info


def top_values(nn, k=6):
    vc = nn.value_counts().head(k)
    return [[str(v), pct(int(c), len(nn))] for v, c in vc.items()]


def late_arrivals(df, table):
    col = EVENT_DATE.get(table)
    if not col or col not in df:
        return None
    ev = pd.to_datetime(df[col], errors="coerce", format="ISO8601").dt.normalize()
    pr = pd.to_datetime(df["_process_date"])
    lag = (pr - ev).dt.days.dropna()
    return {
        "columna_evento": col,
        "pct_tardias": pct(int((lag > 0).sum()), len(lag)),
        "pct_adelantadas": pct(int((lag < 0).sum()), len(lag)),
        "max_retraso_dias": int(lag.max()) if len(lag) else 0,
    }


def orphan_report(df, key_sets):
    out = {}
    for col, (ref_table, _) in FOREIGN_KEYS.items():
        if col not in df or ref_table not in key_sets:
            continue
        vals = df[col].dropna()
        if vals.empty:
            continue
        orphans = int((~vals.isin(key_sets[ref_table])).sum())
        out[col] = {"ref": ref_table, "huerfanos": orphans, "pct": pct(orphans, len(vals))}
    return out


def load_key_sets():
    keys = {}
    for table in {ref for ref, _ in FOREIGN_KEYS.values()}:
        path = parquet_path(table)
        if os.path.exists(path):
            pk = PRIMARY_KEYS[table]
            keys[table] = set(pq.read_table(path, columns=[pk])[pk].drop_null().to_pylist())
    return keys


def fmt_detail(c):
    kind = c.get("kind")
    parts = []
    if kind in ("categórica", "booleano", "numérico") and c.get("top"):
        parts.append(", ".join(f"{v} {p}%" for v, p in c["top"]))
    if kind == "booleano":
        parts.append(f"True {c['pct_true']}%")
    if kind == "numérico":
        parts.append(f"rango {c['min']:g} → {c['max']:g}, mediana {c['p50']:g}")
        if c["no_numericos"]:
            parts.append(f"⚠ {c['no_numericos']} no numéricos")
    if kind == "fecha":
        parts.append(f"{c['min'][:10]} → {c['max'][:10]}")
        if c["no_parseables"]:
            parts.append(f"⚠ {c['no_parseables']} no parseables")
    if kind == "texto":
        parts.append(f"largo prom. {c['largo_promedio']:.0f} car.")
    if c.get("null_like"):
        parts.append(f"⚠ {c['null_like']} textos tipo NULL")
    if c.get("espacios_extremos"):
        parts.append(f"⚠ {c['espacios_extremos']} con espacios")
    return "; ".join(parts).replace("|", "/")


def to_markdown(results):
    lines = ["# Perfil de datos: LATAM Bank (capa bronze)", "",
             "Generado por `analysis/profile_tables.py`. Tablas >1M de filas: muestra por días completos.", ""]
    for table, r in results.items():
        lines += [f"## {table}", "",
                  f"- **Filas:** {r['rows']:,} ({r['lectura']}) · **Columnas:** {len(r['columns'])}",
                  f"- **Duplicados exactos:** {r['dup_rows']:,} ({r['dup_rows_pct']}%)"
                  + (f" · **PK `{r['pk']}` repetida:** {r['dup_pk']:,} ({r['dup_pk_pct']}%)" if r.get("pk") else "")]
        if r.get("late"):
            la = r["late"]
            lines.append(f"- **Llegadas tardías** (`_process_date` > `{la['columna_evento']}`): {la['pct_tardias']}%"
                         f" · máx. {la['max_retraso_dias']} días · adelantadas: {la['pct_adelantadas']}%")
        if r.get("orphans"):
            lines.append("- **FK huérfanas:** " + ", ".join(
                f"`{k}`→{v['ref']}: {v['huerfanos']:,} ({v['pct']}%)" for k, v in r["orphans"].items()))
        lines += ["", "| Columna | Tipo | Nulos % | Distintos | Detalle |", "|---|---|---|---|---|"]
        for name, c in r["columns"].items():
            lines.append(f"| `{name}` | {c.get('kind')} | {c['null_pct']} | {c['distinct']:,} | {fmt_detail(c)} |")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", nargs="*")
    args = ap.parse_args()
    tables = args.tables or sorted(f[:-8] for f in os.listdir(BRONZE_DIR) if f.endswith(".parquet"))

    key_sets = load_key_sets()
    results = {}
    for table in tables:
        print(f"[{table}] perfilando...", flush=True)
        df, total, lectura = load(table)
        cols = [c for c in df.columns if c not in LINEAGE]
        pk = PRIMARY_KEYS.get(table)
        dup_rows = int(df.duplicated(subset=cols).sum())
        r = {"rows": total, "lectura": lectura, "sample_rows": len(df), "pk": pk,
             "dup_rows": dup_rows, "dup_rows_pct": pct(dup_rows, len(df))}
        if pk:
            dup_pk = int(df[pk].duplicated().sum())
            r.update({"dup_pk": dup_pk, "dup_pk_pct": pct(dup_pk, len(df))})
        r["late"] = late_arrivals(df, table)
        r["orphans"] = orphan_report(df.drop(columns=[pk]) if pk else df, key_sets)
        r["columns"] = {c: profile_column(df[c], c) for c in cols}
        results[table] = r

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(to_markdown(results))
    print(f"\nListo: {OUT_MD} y {OUT_JSON}")


if __name__ == "__main__":
    main()
