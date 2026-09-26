"""Silver: bronze (todo STRING) -> tablas tipadas, normalizadas, deduplicadas y con banderas dq_.

Cada tabla se define en sql/silver/<tabla>.sql. Se construye en data/warehouse.duckdb
(esquema silver) y se exporta a data/silver/<tabla>.parquet. Es una reconstrucción completa,
determinista e idempotente: correrla dos veces con los mismos datos da el mismo resultado.

Uso:
  python -m pipeline.silver                     # todas las tablas
  python -m pipeline.silver --tables customers  # solo algunas (respetando dependencias)
"""
import argparse
import os
import time

from pipeline import config, warehouse

# Orden de construcción: dimensiones antes que los hechos que las cruzan.
# (tabla silver, tabla bronze de origen)
ORDER = [
    ("exchange_rates", "daily_exchange_rates"),
    ("branches", "branches"),
    ("service_agents", "service_agents"),
    ("customers", "customers"),
    ("products", "products"),
    ("marketing_campaigns", "marketing_campaigns"),
    ("transactions", "transactions"),
    ("call_center_interactions", "call_center_interactions"),
    ("call_transcripts", "call_transcripts"),
    ("satisfaction_surveys", "satisfaction_surveys"),
    ("complaints", "complaints"),
    ("campaign_sends", "campaign_sends"),
    ("digital_events", "digital_events"),
]


def run(con, tables=None):
    available = set(warehouse.register_bronze(con))
    counts = {}
    for name, source in ORDER:
        if tables and name not in tables:
            continue
        if source not in available:
            print(f"[silver:{name}] falta bronze.{source}, se omite")
            continue
        t0 = time.time()
        n = warehouse.run_sql_file(con, os.path.join(config.SQL_DIR, "silver", f"{name}.sql"), "silver", name)
        warehouse.export_parquet(con, "silver", name, config.SILVER_DIR)
        counts[name] = n
        print(f"[silver:{name}] {n:,} filas ({time.time() - t0:.0f}s)", flush=True)
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
