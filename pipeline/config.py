"""Configuración central: rutas, parámetros y supuestos documentados.

Los valores sensibles (bucket S3) se leen de variables de entorno o de un archivo .env
en la raíz del proyecto (no versionado; ver .env.example).
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv(path=os.path.join(ROOT, ".env")):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# Rutas
DATA_DIR = os.path.join(ROOT, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
BRONZE_DIR = os.path.join(DATA_DIR, "bronze")
SILVER_DIR = os.path.join(DATA_DIR, "silver")
GOLD_DIR = os.path.join(DATA_DIR, "gold")
WAREHOUSE = os.path.join(DATA_DIR, "warehouse.duckdb")
# Carpeta temporal propia (con el PID) para que otros procesos DuckDB no borren nuestros temporales.
TMP_DIR = os.path.join(DATA_DIR, "tmp_pipeline", str(os.getpid()))
SQL_DIR = os.path.join(ROOT, "sql")
CONTRACTS = os.path.join(ROOT, "contracts", "silver.yml")
DOCS_DIR = os.path.join(ROOT, "docs")

# Fuentes externas
S3_BUCKET = os.environ.get("S3_BUCKET")  # s3://<bucket> entregado por los organizadores
AWS_PROFILE = os.environ.get("AWS_PROFILE", "factored")
GCP_PROJECT = os.environ.get("GCP_PROJECT", "hackathon-datos-factored")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "US")
BQ_EXCLUDE = {"digital_events"}  # 15.6M filas sin señal: solo local, para no pasar los 10 GB del sandbox

# Motor local
DUCKDB_MEMORY = os.environ.get("DUCKDB_MEMORY", "3GB")
DUCKDB_THREADS = int(os.environ.get("DUCKDB_THREADS", "6"))

# Parámetros del dominio (evidencia en docs/hallazgos.md)
SNAPSHOT_DATE = "2026-06-17"  # último process_date del dataset: "hoy" para ventanas de 90 días
# amount_usd del dataset = amount / tasa FIJA (no usa la tabla fx diaria). MXN no aparece en tx:
# su tasa (~17) es la mediana USD->MXN de la tabla fx y solo se usa para ingresos y reclamos.
USD_RATES = {"USD": 1.0, "COP": 4000.0, "ARS": 350.0, "MXN": 17.0}
INCOME_CURRENCY = {"México": "MXN", "Colombia": "COP", "Argentina": "ARS"}
FRAUD_SCORE_HIGH = 30  # fraud_score > 30 => 100% fraude confirmado; <= 30 no aporta información
# Supuesto de negocio (NO viene del dataset): costo total de un minuto de agente en LATAM.
AGENT_COST_PER_MINUTE_USD = float(os.environ.get("AGENT_COST_PER_MINUTE_USD", "0.15"))

SQL_PARAMS = {
    "snapshot_date": SNAPSHOT_DATE,
    "usd_rate_COP": USD_RATES["COP"],
    "usd_rate_ARS": USD_RATES["ARS"],
    "usd_rate_MXN": USD_RATES["MXN"],
    "fraud_score_high": FRAUD_SCORE_HIGH,
    "agent_cost_per_minute_usd": AGENT_COST_PER_MINUTE_USD,
}
