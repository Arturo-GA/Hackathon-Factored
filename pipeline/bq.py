"""Utilidades de BigQuery compartidas por la carga de bronze y la publicación de silver/gold."""
from google.cloud import bigquery

from pipeline import config


def client():
    return bigquery.Client(project=config.GCP_PROJECT)


def ensure_dataset(bq, dataset):
    ds = bigquery.Dataset(f"{config.GCP_PROJECT}.{dataset}")
    ds.location = config.BQ_LOCATION
    bq.create_dataset(ds, exists_ok=True)
    return f"{config.GCP_PROJECT}.{dataset}"


def upload_parquet(bq, table_id, parquet_path, expected_rows, cluster_by=None):
    """Carga un Parquet reemplazando la tabla y verifica el conteo de filas.

    Se usa clustering (no partición por fecha): en el sandbox las particiones con más de
    60 días expiran, y las fechas del dataset (2023-2026) se borrarían al cargar.
    """
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    if cluster_by:
        job_config.clustering_fields = cluster_by
    with open(parquet_path, "rb") as fh:
        bq.load_table_from_file(fh, table_id, job_config=job_config).result()
    loaded = bq.get_table(table_id).num_rows
    if loaded != expected_rows:
        raise RuntimeError(f"{table_id}: BigQuery tiene {loaded} filas, se esperaban {expected_rows}")
    return loaded


def storage_gb(bq, datasets=("bronze", "silver", "gold")):
    total = 0
    for ds in datasets:
        try:
            for t in bq.list_tables(f"{config.GCP_PROJECT}.{ds}"):
                total += bq.get_table(t).num_bytes or 0
        except Exception:  # dataset inexistente
            pass
    return total / 1e9
