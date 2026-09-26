"""Gold: tablas de consumo a partir de silver (análisis del call center y herramientas del agente).

Cada tabla se define en sql/gold/<tabla>.sql; además se publica gold.dq_scorecard con el último
resultado de calidad. Exporta a data/gold/<tabla>.parquet.

Uso:
  python -m pipeline.gold
"""
import argparse
import os
import time

from pipeline import config, warehouse

TABLES = [
    "cc_demand_daily",
    "cc_weekday_profile",
    "cc_category_baseline",
    "customer_profile",
    "customer_cards",
    "transactions_enriched",
    "complaints_baseline",
    "agents_routing",
    "fraud_rule_eval",
]


def run(con, tables=None):
    counts = {}
    for name in TABLES:
        if tables and name not in tables:
            continue
        t0 = time.time()
        n = warehouse.run_sql_file(con, os.path.join(config.SQL_DIR, "gold", f"{name}.sql"), "gold", name)
        warehouse.export_parquet(con, "gold", name, config.GOLD_DIR)
        counts[name] = n
        print(f"[gold:{name}] {n:,} filas ({time.time() - t0:.0f}s)", flush=True)
    has_dq = con.execute("SELECT COUNT(*) FROM information_schema.tables "
                         "WHERE table_schema = 'quality' AND table_name = 'dq_results'").fetchone()[0]
    if has_dq and (not tables or "dq_scorecard" in tables):
        con.execute("CREATE OR REPLACE TABLE gold.dq_scorecard AS SELECT * FROM quality.dq_results")
        warehouse.export_parquet(con, "gold", "dq_scorecard", config.GOLD_DIR)
        counts["dq_scorecard"] = con.execute("SELECT COUNT(*) FROM gold.dq_scorecard").fetchone()[0]
        print(f"[gold:dq_scorecard] {counts['dq_scorecard']:,} filas", flush=True)
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", nargs="*")
    args = ap.parse_args()
    con = warehouse.connect()
    run(con, args.tables)
    con.close()


if __name__ == "__main__":
    main()
