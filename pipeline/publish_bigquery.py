"""Publica silver y gold en BigQuery (datasets silver y gold del proyecto GCP).

  * Excluye config.BQ_EXCLUDE (digital_events: 15.6M filas sin señal) para no pasar los 10 GB del sandbox.
  * gold.transactions_enriched se publica como VISTA sobre silver.transactions (no ocupa almacenamiento).
  * Las tablas grandes se agrupan (clustering) por process_date.
  * Verifica el conteo de filas de cada tabla y el almacenamiento total del proyecto.

Uso:
  python -m pipeline.publish_bigquery                 # silver + gold
  python -m pipeline.publish_bigquery --layers gold
"""
import argparse
import os
import re

import pyarrow.parquet as pq

from pipeline import bq as bqu
from pipeline import config, warehouse

VIEWS = {"transactions_enriched"}  # gold que se crean como vistas en BigQuery
LIMIT_GB = 9.7  # margen bajo el límite de 10 GB del sandbox

# Prioridad de publicación de silver (si faltara espacio, lo más útil queda publicado primero).
SILVER_PRIORITY = ["customers", "products", "call_center_interactions", "satisfaction_surveys", "complaints",
                   "service_agents", "branches", "exchange_rates", "marketing_campaigns", "call_transcripts",
                   "transactions", "campaign_sends"]


def bq_view_sql(name):
    sql = warehouse.render(open(os.path.join(config.SQL_DIR, "gold", f"{name}.sql"), encoding="utf-8").read())
    return re.sub(r"\bsilver\.(\w+)", lambda m: f"`{config.GCP_PROJECT}.silver.{m.group(1)}`", sql)


def publish_layer(bq, layer, names):
    dataset = bqu.ensure_dataset(bq, layer)
    folder = config.SILVER_DIR if layer == "silver" else config.GOLD_DIR
    for name in names:
        if name in config.BQ_EXCLUDE:
            print(f"[publish:{layer}.{name}] excluida (solo local)")
            continue
        table_id = f"{dataset}.{name}"
        if layer == "gold" and name in VIEWS:
            from google.cloud import bigquery
            bq.delete_table(table_id, not_found_ok=True)
            view = bigquery.Table(table_id)
            view.view_query = bq_view_sql(name)
            bq.create_table(view)
            print(f"[publish:{layer}.{name}] vista creada", flush=True)
            continue
        path = os.path.join(folder, f"{name}.parquet")
        pf = pq.ParquetFile(path)
        used = bqu.storage_gb(bq)
        if used > LIMIT_GB:
            print(f"[publish:{layer}.{name}] OMITIDA: el proyecto ya usa {used:.2f} GB (límite sandbox 10 GB)")
            continue
        cluster = ["process_date"] if "process_date" in pf.schema_arrow.names and pf.metadata.num_rows > 100_000 else None
        bqu.upload_parquet(bq, table_id, path, pf.metadata.num_rows, cluster)
        print(f"[publish:{layer}.{name}] {pf.metadata.num_rows:,} filas verificadas", flush=True)


def run(layers=("silver", "gold")):
    bq = bqu.client()
    if "silver" in layers:
        available = {f[:-8] for f in os.listdir(config.SILVER_DIR) if f.endswith(".parquet")}
        publish_layer(bq, "silver", [t for t in SILVER_PRIORITY if t in available])
    if "gold" in layers:
        names = sorted(f[:-8] for f in os.listdir(config.GOLD_DIR) if f.endswith(".parquet"))
        publish_layer(bq, "gold", names)
    print(f"Almacenamiento total del proyecto (bronze+silver+gold): {bqu.storage_gb(bq):.2f} GB")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--layers", nargs="*", default=["silver", "gold"])
    run(ap.parse_args().layers)


if __name__ == "__main__":
    main()
