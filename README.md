# Hackathon Factored 2026 — datos LATAM Bank

Tratamiento de datos (bronze → silver → gold) y hallazgos del dataset LATAM Bank para el
Factored AI & Data Hackathon 2026 (sistema de atención al cliente bancario con IA).

**Los datos no están en este repo** (acceso restringido a participantes). Aquí va el código para
descargarlos y procesarlos, los contratos de calidad y los reportes con estadísticas agregadas.

## Estado del proyecto (28 sep 2026)

El proyecto del equipo es **Expediente Vivo v2** y vive en el repo del equipo: https://github.com/DDR2AS/factored-hackathon-2026-Datti (RUNBOOK.md, DECISIONS.md, INTERFACES.md, STATUS.md, plan en `docs/plan/expediente-vivo-v2.html`). Este repo queda como repo personal: pipeline v1.4, análisis de la data y documentos de diseño v1.4.

- [docs/alineacion_v2.md](docs/alineacion_v2.md): qué cambió de v1.4 a v2, quién es dueño de qué, reglas de trabajo del equipo y puntos a aclarar.
- Históricos v1.4: docs/proyecto_expediente_vivo.md, docs/arquitectura_detallada.md, los diagramas y los .docx de docs/.

## Documentos

- [docs/tratamiento_datos.md](docs/tratamiento_datos.md): cómo se procesan los datos, capa por capa y tabla por tabla.
- [docs/hallazgos.md](docs/hallazgos.md): qué encontramos (call center primero) y qué implica para la solución.
- [docs/dq_report.md](docs/dq_report.md): resultado de los 194 checks de calidad (generado).
- Análisis de soporte: [data_profile.md](docs/data_profile.md) (perfil de cada columna),
  [signal_checks.md](docs/signal_checks.md) (1ª pasada de señal), [deep_signal.md](docs/deep_signal.md)
  (2ª pasada con cruces), [hallazgos_detalle.md](docs/hallazgos_detalle.md) (3ª pasada, verificada por agentes).

## Estructura

```
pipeline/     código del pipeline (extract_s3, bronze, silver, quality, gold, publish_bigquery, run)
sql/silver/   una transformación SQL por tabla (tipado, limpieza, banderas dq_)
sql/gold/     tablas de consumo (call center, cliente, tarjetas, transacciones, reclamos, fraude)
contracts/    contratos de datos de silver (llaves, valores permitidos, rangos, FK, reglas)
analysis/     scripts de perfilado y búsqueda de señal (pass3/ = scripts de los agentes)
docs/         documentación y reportes
```

## Cómo correrlo

Requisitos: Python 3.12, AWS CLI (credenciales del hackathon) y, para publicar, Google Cloud SDK.

```bash
python -m venv .venv
source .venv/Scripts/activate          # Windows Git Bash (Linux/Mac: .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env                   # completar S3_BUCKET
aws configure --profile factored       # credenciales entregadas por los organizadores
```

```bash
python -m pipeline.run --steps extract bronze silver quality gold   # todo local (~10 min)
python -m pipeline.run --steps silver quality gold                   # re-procesar sin re-leer CSV
python -m pipeline.publish_bigquery                                  # publicar silver y gold
```

Resultado local: `data/bronze|silver|gold/*.parquet` y `data/warehouse.duckdb` (esquemas bronze,
silver, gold, quality; se puede abrir con DBeaver o `duckdb`). En BigQuery: datasets `bronze`,
`silver` y `gold` del proyecto `hackathon-datos-factored`.

Antes de hacer commit de reportes: `python analysis/sanitize_docs.py` (enmascara IDs y emails).
