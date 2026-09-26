"""Calidad: valida la capa silver contra contracts/silver.yml.

Resultado:
  - tabla quality.dq_results en el warehouse (una fila por check)
  - docs/dq_report.md (legible)
  - código de salida 1 si algún check de severidad 'error' falla

Uso:
  python -m pipeline.quality
"""
import datetime as dt
import os
import sys

import pandas as pd
import yaml

from pipeline import config, warehouse


def lit(v):
    return "'" + str(v).replace("'", "''") + "'"


def checks_for(table, spec, lag_days):
    """Genera (check, columna, severidad, sql que cuenta filas que fallan, descripción)."""
    t = f"silver.{table} AS t"
    pk = spec.get("primary_key")
    if pk:
        cols = pk if isinstance(pk, list) else [pk]
        cl = ", ".join(cols)
        yield ("primary_key_unica", cl, "error",
               f"SELECT COALESCE(SUM(n - 1), 0) FROM (SELECT COUNT(*) n FROM {t} GROUP BY {cl} HAVING COUNT(*) > 1)", "")
        yield ("primary_key_no_nula", cl, "error",
               f"SELECT COUNT(*) FROM {t} WHERE " + " OR ".join(f"{c} IS NULL" for c in cols), "")
    for col in spec.get("unique", []):
        yield ("unico", col, "error",
               f"SELECT COALESCE(SUM(n - 1), 0) FROM (SELECT COUNT(*) n FROM {t} WHERE {col} IS NOT NULL GROUP BY {col} HAVING COUNT(*) > 1)", "")
    if "min_rows" in spec:
        yield ("filas_minimas", "", "error",
               f"SELECT CASE WHEN COUNT(*) < {spec['min_rows']} THEN 1 ELSE 0 END FROM {t}", f">= {spec['min_rows']:,} filas")
    for col in spec.get("not_null", []):
        yield ("no_nulo", col, "error", f"SELECT COUNT(*) FROM {t} WHERE {col} IS NULL", "")
    for col, values in (spec.get("accepted_values") or {}).items():
        yield ("valores_permitidos", col, "error",
               f"SELECT COUNT(*) FROM {t} WHERE {col} IS NOT NULL AND CAST({col} AS VARCHAR) NOT IN ({', '.join(lit(v) for v in values)})",
               ", ".join(map(str, values)))
    for col, (lo, hi) in (spec.get("ranges") or {}).items():
        conds = ([f"{col} < {lo}"] if lo is not None else []) + ([f"{col} > {hi}"] if hi is not None else [])
        yield ("rango", col, "error", f"SELECT COUNT(*) FROM {t} WHERE {' OR '.join(conds)}", f"[{lo}, {hi}]")
    for fk in spec.get("foreign_keys", []):
        ref_table, ref_col = fk["ref"].split(".")
        yield ("llave_foranea", fk["column"], fk.get("severity", "error"),
               f"SELECT COUNT(*) FROM {t} WHERE {fk['column']} IS NOT NULL AND {fk['column']} NOT IN (SELECT {ref_col} FROM silver.{ref_table})",
               f"-> {fk['ref']}")
    for rule in spec.get("rules", []):
        yield (rule["name"], "", rule.get("severity", "error"),
               f"SELECT COUNT(*) FROM {t} WHERE {rule['when']}", rule.get("description", ""))
    if spec.get("freshness"):
        col = spec["freshness"]
        yield ("frescura", col, "warn",
               f"SELECT CASE WHEN MAX({col}) < DATE '{config.SNAPSHOT_DATE}' - INTERVAL {lag_days} DAY THEN 1 ELSE 0 END FROM {t}",
               f"MAX({col}) >= {config.SNAPSHOT_DATE} - {lag_days} día(s)")


def run(con):
    contracts = yaml.safe_load(open(config.CONTRACTS, encoding="utf-8"))
    lag = contracts.get("freshness_max_lag_days", 1)
    run_at = dt.datetime.now(dt.timezone.utc)
    rows = []
    for table, spec in contracts["tables"].items():
        total = con.execute(f"SELECT COUNT(*) FROM silver.{table}").fetchone()[0]
        for check, column, severity, sql, desc in checks_for(table, spec, lag):
            failed = int(con.execute(sql).fetchone()[0] or 0)
            status = "PASS" if failed == 0 else ("FAIL" if severity == "error" else "WARN")
            rows.append({"run_at": run_at, "table_name": table, "check_name": check, "column_name": column,
                         "severity": severity, "failed_rows": failed, "total_rows": total,
                         "failed_pct": round(100 * failed / total, 3) if total else 0.0,
                         "status": status, "description": desc})
        print(f"[quality:{table}] {sum(r['table_name'] == table for r in rows)} checks", flush=True)
    df = pd.DataFrame(rows)
    con.register("dq_df", df)
    con.execute("CREATE OR REPLACE TABLE quality.dq_results AS SELECT * FROM dq_df")
    con.unregister("dq_df")
    write_report(df)
    return df


def write_report(df):
    lines = ["# Reporte de calidad de datos (capa silver)", "",
             f"Generado por `pipeline/quality.py` a partir de `contracts/silver.yml` ({df['run_at'].iloc[0]:%Y-%m-%d %H:%M} UTC).", "",
             f"- Checks: {len(df)} · PASS: {(df.status == 'PASS').sum()} · WARN (defectos conocidos): {(df.status == 'WARN').sum()} "
             f"· FAIL (rompen contrato): {(df.status == 'FAIL').sum()}", "",
             "## Checks con problemas", "",
             "| Tabla | Check | Columna | Severidad | Filas afectadas | % | Estado | Detalle |",
             "|---|---|---|---|---|---|---|---|"]
    bad = df[df.status != "PASS"].sort_values(["status", "table_name", "failed_pct"], ascending=[True, True, False])
    for r in bad.itertuples():
        lines.append(f"| {r.table_name} | {r.check_name} | {r.column_name} | {r.severity} | {r.failed_rows:,} | "
                     f"{r.failed_pct} | {r.status} | {r.description} |")
    lines += ["", "## Checks que pasan (por tabla)", ""]
    for table, g in df[df.status == "PASS"].groupby("table_name"):
        lines.append(f"- **{table}**: " + ", ".join(sorted(set(f"{c}({col})" if col else c for c, col in zip(g.check_name, g.column_name)))))
    os.makedirs(config.DOCS_DIR, exist_ok=True)
    with open(os.path.join(config.DOCS_DIR, "dq_report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    con = warehouse.connect()
    df = run(con)
    con.close()
    print(df["status"].value_counts().to_string())
    fails = df[df.status == "FAIL"]
    if len(fails):
        print("\nChecks que rompen contrato:\n" + fails[["table_name", "check_name", "column_name", "failed_rows"]].to_string(index=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
