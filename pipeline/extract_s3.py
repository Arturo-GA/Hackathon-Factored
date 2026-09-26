"""Extract: sincroniza los CSV del bucket S3 de los organizadores a data/raw.

Usa `aws s3 sync` (incremental: solo baja archivos nuevos o modificados, y si se corta se
retoma con el mismo comando). Las credenciales NO van en el código: se configuran con
`aws configure --profile factored` y el bucket se define en .env (S3_BUCKET=s3://...).

Uso:
  python -m pipeline.extract_s3                         # todas las tablas
  python -m pipeline.extract_s3 --tables complaints     # solo algunas
"""
import argparse
import shutil
import subprocess
import sys

from pipeline import config

DAILY_TABLES = ["call_center_interactions", "call_transcripts", "campaign_sends", "complaints",
                "digital_events", "satisfaction_surveys", "transactions"]
SNAPSHOT_TABLES = ["branches", "customers", "daily_exchange_rates", "marketing_campaigns",
                   "products", "service_agents"]


def aws_cli():
    exe = shutil.which("aws") or r"C:\Program Files\Amazon\AWSCLIV2\aws.exe"
    return exe


def sync(tables):
    if not config.S3_BUCKET:
        sys.exit("Falta S3_BUCKET (defínelo en .env; ver .env.example)")
    base = config.S3_BUCKET.rstrip("/") + "/data/"
    snapshots = [t for t in tables if t in SNAPSHOT_TABLES]
    if snapshots:
        cmd = [aws_cli(), "s3", "sync", base, config.RAW_DIR, "--exclude", "*"]
        for t in snapshots:
            cmd += ["--include", f"{t}.csv"]
        subprocess.run(cmd + ["--only-show-errors", "--profile", config.AWS_PROFILE], check=True)
    for t in tables:
        if t in DAILY_TABLES:
            print(f"[extract] {t}", flush=True)
            subprocess.run([aws_cli(), "s3", "sync", base + t + "/", f"{config.RAW_DIR}/{t}",
                            "--only-show-errors", "--profile", config.AWS_PROFILE], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tables", nargs="*", default=SNAPSHOT_TABLES + DAILY_TABLES)
    sync(ap.parse_args().tables)


if __name__ == "__main__":
    main()
