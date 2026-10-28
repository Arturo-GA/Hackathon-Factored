# Factored AI & Data Hackathon 2026 — LATAM Bank data pipeline

Data engineering and analysis for the [Factored AI & Data Hackathon 2026](https://factored.ai) challenge: an AI-powered customer-service system for a synthetic bank ("LATAM Bank"). This repo is my personal contribution to the team project **Expediente Vivo** (team repo: [DDR2AS/factored-hackathon-2026-Datti](https://github.com/DDR2AS/factored-hackathon-2026-Datti)): the pipeline that turns 13 raw CSV tables from S3 into typed, quality-checked tables in DuckDB and BigQuery, plus the data analysis that shaped the solution.

**The data itself is not in this repo** (restricted to participants). What is here: the code to download and process it, the data contracts, and the reports with aggregated statistics.

## What was built

- **Medallion pipeline** (`pipeline/`): `extract_s3 → bronze → silver → quality → gold`, runnable end to end in ~10 min locally, with a `publish_bigquery` step for the shared warehouse.
  - *Bronze*: raw CSVs as Parquet, untouched.
  - *Silver* (`sql/silver/`): one SQL transformation per table — typing, cleaning, `dq_` flags for known defects, FX normalisation.
  - *Gold* (`sql/gold/`): consumption tables for the agent and the dashboards — call-center demand and weekday profile, customer profile and cards, enriched transactions, complaint and fraud baselines, agent routing.
- **Data contracts** (`contracts/silver.yml`): keys, allowed values, ranges, foreign keys and business rules for every silver table. `pipeline/quality.py` runs them: **194 checks · 159 pass · 35 warn (documented defects) · 0 fail**. Report in [docs/dq_report.md](docs/dq_report.md).
- **Analysis in three passes** (`analysis/`, reports in `docs/`):
  1. Column-level profile and first signal checks ([data_profile.md](docs/data_profile.md), [signal_checks.md](docs/signal_checks.md)).
  2. Cross-table joins with time windows in DuckDB ([deep_signal.md](docs/deep_signal.md)).
  3. 38 findings each reproduced by one script and challenged by another ([hallazgos_detalle.md](docs/hallazgos_detalle.md)).

  Main conclusion ([hallazgos.md](docs/hallazgos.md)): the dataset is synthetic and generated mostly as independent draws plus a few exact rules (e.g. first-contact resolution depends only on the contact reason, AUC 0.76; weekend demand is exactly half of weekday). That ruled out text/credit/churn models and focused the team on call-center demand baselines, exact rule checks and a consistent data layer for the agent.
- **Design documents** for the v1.4 solution: [architecture](docs/arquitectura_detallada.md), [conversation flow](docs/flujo_conversacion.svg), [project proposal](docs/proyecto_expediente_vivo.md), and the [alignment note](docs/alineacion_v2.md) describing what changed in v2 and who owns what.

Reports and documents are in Spanish (the hackathon's working language).

## Structure

```
pipeline/     extract_s3, bronze, silver, quality, gold, publish_bigquery, run (CLI)
sql/silver/   one SQL transformation per table (typing, cleaning, dq_ flags)
sql/gold/     consumption tables (call center, customer, cards, transactions, complaints, fraud)
contracts/    silver data contracts (keys, allowed values, ranges, FKs, rules)
analysis/     profiling and signal-search scripts (pass3/ = per-finding reproduce/refute scripts)
docs/         reports, findings, design documents and diagrams
```

## Run it

Requirements: Python 3.12, AWS CLI (hackathon credentials) and, to publish, the Google Cloud SDK.

```bash
python -m venv .venv
source .venv/Scripts/activate          # Windows Git Bash (Linux/Mac: .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env                   # fill in S3_BUCKET
aws configure --profile factored       # credentials provided by the organisers
```

```bash
python -m pipeline.run --steps extract bronze silver quality gold   # everything local (~10 min)
python -m pipeline.run --steps silver quality gold                   # reprocess without re-reading the CSVs
python -m pipeline.publish_bigquery                                  # publish silver and gold
```

Local output: `data/bronze|silver|gold/*.parquet` and `data/warehouse.duckdb` (schemas bronze, silver, gold, quality; open with DBeaver or `duckdb`). In BigQuery: datasets `bronze`, `silver` and `gold` of the `hackathon-datos-factored` project.

Before committing reports: `python analysis/sanitize_docs.py` (masks IDs and e-mails).
