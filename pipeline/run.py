"""Orquestador del pipeline completo.

Pasos (en orden): extract -> bronze -> silver -> quality -> gold -> publish
Por defecto corre los pasos locales (bronze, silver, quality, gold). extract necesita S3_BUCKET y
el perfil AWS; publish necesita credenciales de Google Cloud (gcloud auth application-default login).

Uso:
  python -m pipeline.run                                   # bronze -> gold (local)
  python -m pipeline.run --steps extract bronze silver quality gold publish
  python -m pipeline.run --steps silver quality gold       # re-procesar sin re-leer CSV
"""
import argparse
import sys
import time

from pipeline import bronze, gold, quality, silver, warehouse

ALL_STEPS = ["extract", "bronze", "silver", "quality", "gold", "publish"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", nargs="*", default=["bronze", "silver", "quality", "gold"], choices=ALL_STEPS)
    steps = [s for s in ALL_STEPS if s in ap.parse_args().steps]
    t0 = time.time()

    if "extract" in steps:
        from pipeline import extract_s3
        extract_s3.sync(extract_s3.SNAPSHOT_TABLES + extract_s3.DAILY_TABLES)
    if "bronze" in steps:
        bronze.run()

    con = None
    if {"silver", "quality", "gold"} & set(steps):
        con = warehouse.connect()
    if "silver" in steps:
        silver.run(con)
    if "quality" in steps:
        df = quality.run(con)
        fails = df[df.status == "FAIL"]
        print(f"[quality] {len(df)} checks: {(df.status == 'PASS').sum()} PASS, "
              f"{(df.status == 'WARN').sum()} WARN, {len(fails)} FAIL")
        if len(fails):
            print(fails[["table_name", "check_name", "column_name", "failed_rows"]].to_string(index=False))
            sys.exit("El contrato de datos no se cumple: se detiene antes de gold/publish.")
    if "gold" in steps:
        gold.run(con)
    if con:
        con.close()
    if "publish" in steps:
        from pipeline import publish_bigquery
        publish_bigquery.run()
    print(f"Pipeline OK ({', '.join(steps)}) en {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
