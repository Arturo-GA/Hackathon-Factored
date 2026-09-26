"""Conexión al warehouse local (DuckDB) y utilidades compartidas por silver, gold y calidad.

data/warehouse.duckdb tiene cuatro esquemas:
  bronze  -> vistas sobre data/bronze/*.parquet (sin copiar datos)
  silver  -> tablas tipadas y limpias
  gold    -> tablas de consumo (análisis y herramientas del agente)
  quality -> resultados de las validaciones
"""
import os
import re

import duckdb

from pipeline import config


def connect(read_only=False):
    os.makedirs(config.TMP_DIR, exist_ok=True)
    con = duckdb.connect(config.WAREHOUSE, read_only=read_only)
    con.execute(f"SET memory_limit='{config.DUCKDB_MEMORY}'; SET threads={config.DUCKDB_THREADS}; "
                f"SET temp_directory='{config.TMP_DIR.replace(os.sep, '/')}'; SET preserve_insertion_order=false")
    if not read_only:
        for schema in ("bronze", "silver", "gold", "quality"):
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    return con


def register_bronze(con):
    """Crea una vista bronze.<tabla> por cada Parquet de data/bronze."""
    tables = sorted(f[:-8] for f in os.listdir(config.BRONZE_DIR) if f.endswith(".parquet"))
    for t in tables:
        path = os.path.join(config.BRONZE_DIR, f"{t}.parquet").replace(os.sep, "/")
        con.execute(f"CREATE OR REPLACE VIEW bronze.{t} AS SELECT * FROM read_parquet('{path}')")
    return tables


def render(sql, params=None):
    """Reemplaza {{nombre}} por los parámetros de config.SQL_PARAMS."""
    params = {**config.SQL_PARAMS, **(params or {})}

    def sub(m):
        key = m.group(1)
        if key not in params:
            raise KeyError(f"Parámetro SQL desconocido: {key}")
        return str(params[key])

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", sub, sql)


def run_sql_file(con, path, schema, name):
    sql = render(open(path, encoding="utf-8").read())
    con.execute(f"CREATE OR REPLACE TABLE {schema}.{name} AS {sql}")
    return con.execute(f"SELECT COUNT(*) FROM {schema}.{name}").fetchone()[0]


def export_parquet(con, schema, name, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.parquet").replace(os.sep, "/")
    con.execute(f"COPY {schema}.{name} TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    return path
