"""Bronze: copia fiel de los CSV de S3 (todas las columnas STRING) + columnas de linaje.

Pasos:
  1. Valida que todos los archivos de una tabla tengan la misma cabecera (contrato de esquema).
  2. Convierte los CSV de cada tabla a un Parquet en data/bronze/ (con caché por fecha de modificación).
  3. Opcional (--upload): sube cada Parquet al dataset bronze de BigQuery y verifica el conteo.

Linaje agregado: _source_file (ruta relativa del CSV), _process_date (partición year/month/day)
e _ingested_at (momento de la carga).

Uso:
  python -m pipeline.bronze                       # todas las tablas de data/raw
  python -m pipeline.bronze --tables complaints    # solo algunas
  python -m pipeline.bronze --upload               # además sube a BigQuery
"""
import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from pipeline import config

PARTITION_RE = re.compile(r"year=(\d{4})[\\/]month=(\d{2})[\\/]day=(\d{2})")
LINEAGE_FIELDS = [
    pa.field("_source_file", pa.string()),
    pa.field("_process_date", pa.date32()),
    pa.field("_ingested_at", pa.timestamp("us", tz="UTC")),
]
MANIFEST = os.path.join(config.BRONZE_DIR, "_manifest.json")


def discover_tables():
    return sorted(e[:-4] if e.endswith(".csv") else e for e in os.listdir(config.RAW_DIR))


def list_sources(table):
    single = os.path.join(config.RAW_DIR, f"{table}.csv")
    if os.path.isfile(single):
        return [single]
    return sorted(glob.glob(os.path.join(config.RAW_DIR, table, "**", "*.csv"), recursive=True))


def read_header(path):
    # utf-8-sig descarta el BOM (﻿) que traen los CSV del bucket.
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return next(csv.reader(fh))


def process_date_from_path(path):
    m = PARTITION_RE.search(path)
    return dt.date(int(m[1]), int(m[2]), int(m[3])) if m else None


def build_parquet(sources, out_path, ingested_at):
    header = read_header(sources[0])
    schema = pa.schema([pa.field(c, pa.string()) for c in header] + LINEAGE_FIELDS)
    # Solo el campo vacío es NULL: literales como "NULL" o "N/A" se conservan para silver.
    convert = pacsv.ConvertOptions(column_types={c: pa.string() for c in header},
                                   strings_can_be_null=True, null_values=[""])
    parse = pacsv.ParseOptions(newlines_in_values=True)
    read = pacsv.ReadOptions(column_names=header, skip_rows=1)  # nombres validados, sin la cabecera

    rows = 0
    tmp_path = out_path + ".tmp"
    with pq.ParquetWriter(tmp_path, schema) as writer:
        for path in sources:
            file_header = read_header(path)
            if file_header != header:
                raise ValueError(f"Contrato roto en {path}: la cabecera difiere de {sources[0]}.\n"
                                 f"  esperado: {header}\n  recibido: {file_header}")
            t = pacsv.read_csv(path, read_options=read, parse_options=parse, convert_options=convert)
            n = t.num_rows
            rel = os.path.relpath(path, config.RAW_DIR).replace(os.sep, "/")
            t = t.append_column(LINEAGE_FIELDS[0], pa.array([rel] * n, pa.string()))
            t = t.append_column(LINEAGE_FIELDS[1], pa.array([process_date_from_path(path)] * n, pa.date32()))
            t = t.append_column(LINEAGE_FIELDS[2], pa.array([ingested_at] * n, LINEAGE_FIELDS[2].type))
            writer.write_table(t)
            rows += n
    os.replace(tmp_path, out_path)
    return rows, len(header)


def is_fresh(out_path, sources):
    return os.path.exists(out_path) and os.path.getmtime(out_path) >= max(os.path.getmtime(s) for s in sources)


def run(tables=None, upload=False, rebuild=False):
    tables = tables or discover_tables()
    os.makedirs(config.BRONZE_DIR, exist_ok=True)
    ingested_at = dt.datetime.now(dt.timezone.utc)
    manifest = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else {}

    bq = dataset_ref = None
    if upload:
        from pipeline import bq as bqu
        bq = bqu.client()
        dataset_ref = bqu.ensure_dataset(bq, "bronze")

    for table in tables:
        sources = list_sources(table)
        if not sources:
            print(f"[bronze:{table}] sin archivos en {config.RAW_DIR}, se omite", file=sys.stderr)
            continue
        out_path = os.path.join(config.BRONZE_DIR, f"{table}.parquet")
        daily = len(sources) > 1 or process_date_from_path(sources[0]) is not None

        if rebuild or not is_fresh(out_path, sources) or table not in manifest:
            print(f"[bronze:{table}] convirtiendo {len(sources)} CSV a Parquet...", flush=True)
            rows, ncols = build_parquet(sources, out_path, ingested_at)
            manifest[table] = {
                "source_files": len(sources), "rows": rows, "source_columns": ncols,
                "clustered_by": "_process_date" if daily else None,
                "parquet": os.path.relpath(out_path, config.ROOT).replace(os.sep, "/"),
                "built_at": ingested_at.isoformat(),
            }
        else:
            print(f"[bronze:{table}] Parquet al día, se reutiliza", flush=True)

        if bq:
            from pipeline import bq as bqu
            rows = manifest[table]["rows"]
            bqu.upload_parquet(bq, f"{dataset_ref}.{table}", out_path, rows, ["_process_date"] if daily else None)
            manifest[table]["loaded_to"] = f"{dataset_ref}.{table}"
            manifest[table]["loaded_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            print(f"[bronze:{table}] BigQuery OK: {rows:,} filas verificadas", flush=True)

        with open(MANIFEST, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", nargs="*")
    ap.add_argument("--upload", action="store_true", help="Sube bronze a BigQuery")
    ap.add_argument("--rebuild", action="store_true", help="Regenera los Parquet aunque estén al día")
    args = ap.parse_args()
    manifest = run(args.tables, args.upload, args.rebuild)
    for t in args.tables or discover_tables():
        if t in manifest:
            print(f"  {t:<26} {manifest[t]['rows']:>12,} filas  {manifest[t]['source_files']:>5} archivos")


if __name__ == "__main__":
    main()
