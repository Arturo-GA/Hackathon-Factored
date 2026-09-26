"""Utilidades comunes para los scripts behavior_* (conexión DuckDB read-only con límites)."""
import duckdb
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 200)


def connect():
    con = duckdb.connect("data/analysis.duckdb", read_only=True)
    con.execute("SET memory_limit='700MB'; SET threads=2; SET temp_directory='data/duckdb_tmp'; SET preserve_insertion_order=false")
    return con


def q(con, sql):
    return con.execute(sql).df()
