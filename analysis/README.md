# Scripts de análisis

Leen `data/bronze` o `data/analysis.duckdb` (tablas tipadas; se crea con `build_analysis_db.py`).

- `profile_tables.py` → docs/data_profile.md (perfil de cada columna; no lista valores de IDs ni datos personales)
- `signal_checks.py` → docs/signal_checks.md (1ª pasada de señal)
- `deep_signal.py` → docs/deep_signal.md (2ª pasada: cruces entre tablas con DuckDB)
- `pass3/` → scripts de los agentes de la 3ª pasada. Prefijo = lente: `temporal_`, `behavior_`, `amounts_`,
  `fraud_`, `status_`, `cross_`, `ids_` (artefactos del generador), `hunt_` (búsqueda supervisada);
  `verify_<hallazgo>_repro|skeptic` = verificadores. Cada hallazgo de docs/hallazgos_detalle.md indica su script.
- `pass3_report.py` → docs/hallazgos_detalle.md (a partir del resultado del workflow, que no se versiona)
- `sanitize_docs.py` → enmascara IDs/emails en docs antes de publicar
