# Alineación con Expediente Vivo v2 (28 sep 2026)

La fuente de verdad desde el lunes 28 de septiembre es el repo del equipo:
https://github.com/DDR2AS/factored-hackathon-2026-Datti. Ahí están RUNBOOK.md, DECISIONS.md (D1–D12),
INTERFACES.md, STATUS.md y el plan completo en `docs/plan/expediente-vivo-v2.html`.

Este repo (Hackathon-Factored) queda como repo personal de Arturo: el pipeline v1.4, los análisis de la data y
los documentos de diseño v1.4. Lo que diga el repo del equipo manda sobre cualquier documento de aquí.

Orden de lectura para cualquier persona o agente: RUNBOOK.md, AGENTS.md, DECISIONS.md, INTERFACES.md, STATUS.md,
docs/architecture.md, las cuatro skills de `.agents/skills/` y el plan v2 (secciones 1, 3, 4, 5, 6, 13 y 14).

## Fechas

- Lun 28 sep: empieza la implementación. Stand-up 09:00 (se confirman o corrigen D1–D11 y las interfaces), demo interna 21:00 todos los días.
- Mar 29 (M1): ruta B de punta a punta en la URL desplegada.
- Jue 1 oct (M2): tres rutas y todas las pantallas en vivo.
- Sáb 3 oct 18:00 (M3): congelamiento de código.
- Dom 4 (M4): video y slides.
- Lun 5 oct antes del mediodía: entrega (confirmar la hora exacta con los organizadores).

## Qué cambia de v1.4 a v2

| Tema | v1.4 (docs de este repo) | v2 (vigente) |
|---|---|---|
| Alcance profundo | 5 tipos de queja + triaje de 6 motivos | Solo "cargo no reconocido" y "cobro indebido" (40% de los reclamos). App, sucursal y servicio: solo intake y enrutamiento (D1) |
| Clases de intención | ~11 motivos + tipo de queja + urgencia | 9 clases: dispute_charge, dispute_fee, complaint_other, case_status, account_query, lost_card, human_request, out_of_scope, manipulation |
| Encontrar el cargo | Regla (fecha ±1 día, monto ±5%, comercio) | M1: ranker LightGBM LambdaRank calibrado; la regla queda como baseline y respaldo (D3) |
| Clasificador | Embeddings + regresión logística | Mismo modelo (M2), calibrado, umbrales elegidos en validación y guardados en `config/thresholds.yaml` |
| Riesgo | Regla fraud_score > 30 | La regla se mantiene; M3 agrega evidencia de comportamiento y un experimento de un día para ver si mejora |
| Ruta B | Abre caso y lo encola | Además, para disputas de dinero, un investigador G2 (Sonnet 5, solo lectura, ≤12 consultas, ≤90 s) escribe un reporte con citas; un analista aprueba, edita o rechaza (D4) |
| Modelos | Claude Opus 5 para todo | Haiku 4.5 en el chat (G1), Sonnet 5 investigador (G2, comparado con Opus 5 el vie 2), Opus 5 juez offline (G3) (D5) |
| Nube | App Runner, DuckDB, /tick cada 15 min; Google Cloud como plan B | Todo serverless en AWS us-east-2: Lambda, API Gateway, DynamoDB, Step Functions, EventBridge Scheduler, Bedrock, SageMaker. Sin plan B en Google Cloud (D6) |
| Evaluación | Suite de 200+ conversaciones sintéticas | ~240 escenarios sembrados sobre transacciones reales + 150 mensajes escritos a mano por el equipo + 30 adversarios; baseline = v1.4 solo reglas (D7) |
| Despliegue | Día 8 | Desde el día 1: la URL desplegada funciona al final de cada día (D8) |
| Recortes | — | Fuera: notificaciones push, plan B en GCP, la mayoría de clases extra. "Crea tu propio cliente" pasa a opcional (D9) |
| Infraestructura | — | Todo en AWS CDK (Python) en `infra/`, un stage por persona (`expvivo-<stage>-*`), solo por pull request (D12) |
| Front | Streamlit como respaldo | Web estática en S3 + CloudFront. Ojo: Streamlit necesita servidor, así que el respaldo tiene que ser otra opción estática |

Se mantiene de v1.4: el LLM entiende y redacta, las reglas YAML eligen la ruta A/B/C, el gateway aplica permisos (D2);
reglas de completitud, reloj de promesas, modo juez, interruptores de falla y los seis clientes de la demo.

## Quién es dueño de qué (plan v2, sección 13)

- Andrés: cuenta AWS y CDK, usuarios IAM, gateway (`src/gateway/`), cliente LLM (`src/llm/`), ciclo de vida del caso (Step Functions), investigador G2, observabilidad, costos, interruptores de falla.
- Diego: pipeline local en DuckDB por partición (`run_partition(table, date)`), tablas gold y su esquema en `docs/data/gold_tables.md`, exportación a DynamoDB, generador de escenarios, consultas de trazas.
- Cristhian: M1, M2, M3, calibración, arnés de evaluación (`make train`, `make eval`), validación del juez G3.
- Arturo: máquina de estados, reglas YAML de ruta, prompts de G1, modo degradado, coordinación, README, slides y video. Dueño de la interfaz #1 (Chat API) y #3 (registro del caso, con Andrés para el almacenamiento).
- Arturo + Diego: front (chat, tarjeta del caso en vivo, consola del analista, vista de trazas, página de evaluación, modo juez).

## Reglas de trabajo del equipo

- AWS: Andrés administra la cuenta; los demás aún no tienen acceso. Se desarrolla y prueba en local. Para desplegar se pide un usuario IAM a Andrés y se despliega con el CDK del repo, nunca a mano en la consola. El código de la aplicación no llama servicios de AWS; la única llamada hoy es descargar el dataset con `src/etl/ingest_s3_duckdb.py` y la llave de solo lectura en el `.env` local.
- Local contra INTERFACES.md: DuckDB para datos y el proveedor `mock` de `src/llm` para modelos. Nunca dejar fijo un ID de modelo ni un proveedor.
- Secretos y datos nunca van a git. En el repo del equipo `.gitignore` también ignora todos los `*.json` y las carpetas `src/agent/` y `src/analysis/`: lo que quede ahí no se sube. Revisar `git status` después de crear archivos.
- Claim-before-build: pull, leer STATUS, DECISIONS e INTERFACES, y agregar una línea de reclamo a STATUS.md con commit directo a main antes de empezar.
- Boundary-conflict-stop: si el trabajo necesita cambiar una interfaz, parar y proponer el cambio en INTERFACES.md para su dueño. Nunca resolver uno mismo un conflicto en INTERFACES.md.
- Decision-capture: toda decisión que cambie rumbo o alcance va a DECISIONS.md con el motivo en palabras exactas de quien decidió. Los agentes no inventan justificaciones.
- Hold-under-fire: antes de decir que algo funciona, probarlo como un desconocido: sesión expirada, ID de otro cliente, inyección de instrucciones, herramienta caída y la misma solicitud en portugués. Reportar pasó / falló / no probado.
- STATUS.md, DECISIONS.md e INTERFACES.md van con commit directo a main; el código va en rama con pull request.
- Los nombres de los targets del Makefile no se cambian, solo su contenido. En Windows sin make se corre el comando del target.
- Todo el texto de conversaciones y todo el portugués son generados y se marcan como sintéticos. Los mensajes de prueba escritos por el equipo nunca van a entrenamiento ni a prompts.
- El sistema nunca mueve dinero, nunca promete reembolsos, nunca aprueba créditos, y ningún modelo elige la ruta: lo deciden reglas en código.

## Puntos a aclarar en el stand-up (detectados al comparar v1.4, v2 y la data)

1. Sesión: INTERFACES #1 devuelve un `session_token` propio desde `POST /session`, pero el plan y el CDK usan Cognito con JWT. ¿El token del chat es el JWT de Cognito o uno propio? Localmente, ¿quién firma la sesión? (Andrés + Arturo)
2. El registro del caso (#3) no tiene estados para la ruta A (resuelto en el contacto) ni para la ruta C (derivado a humano): solo open → investigating → awaiting_analyst → notified → closed | reopened. Además falta el backend local de casos (en la nube es DynamoDB + Step Functions).
3. La salida de G1 (extracción) no está en INTERFACES. Las reglas de ruta C necesitan señales que no están en los slots de M1 (mención al regulador o acción legal, pedido de compensación, queja sobre una persona) ni en las 9 clases de M2. Propuesta: definir el esquema de salida de G1 con esas señales. Tampoco hay subtipo para complaint_other (app / sucursal / servicio), necesario para las reglas de completitud y la cola.
4. El gateway (#2) no tiene herramienta de perfil del cliente (país, idioma, segmento, zona horaria) ni de casos (`get_case` aparece en el apéndice B del investigador pero no en #2). Falta definir `GatewayContext`.
5. Los fixtures del proveedor mock (`tests/fixtures/llm/`) y cualquier esquema JSON quedarían ignorados por el `.gitignore` del equipo (`*.json`). Hay que acordar la excepción (pregunta abierta en STATUS.md).
6. El cronograma dice "ruta B de punta a punta para Lucía y João" el martes, pero en la demo (sección 12) Lucía es ruta A. Además, un cliente de la demo se llama Andrés, igual que un integrante: conviene renombrarlo para no confundir "el caso de Andrés".
7. La sección 8 del plan menciona "~2% duplicados, ~5% nulos, late arrivals" (viene del resumen de los organizadores). En nuestra verificación sobre la data completa hay 0 duplicados y 0 late arrivals (ver docs/dq_report.md y docs/hallazgos.md). Corregir antes de que llegue al README.
8. El checklist del plan pide subir las consultas detrás de los hallazgos de v1.4 ("100% producto ajeno", "44 variables"). Están en este repo (`analysis/`, `sql/`, `docs/hallazgos_detalle.md`); falta decidir quién las lleva al repo del equipo (Diego tiene esa tarea el domingo 27).
9. El pipeline v1.4 de este repo (bronze/silver/gold, 194 checks, tablas gold customer_profile, transactions_enriched, etc.) es la base que el plan dice que "pasa a Lambda casi igual". Diego lo refactoriza a `run_partition`; hay que acordar si se copia el código de aquí o se reescribe sobre `data/processed/latam_bank.duckdb`.

## Estado de los documentos de este repo

- Vigentes (datos y análisis, no cambian con v2): tratamiento_datos.md, hallazgos.md, hallazgos_detalle.md, dq_report.md, data_profile.md, signal_checks.md, deep_signal.md, analisis_quejas.md.
- Históricos v1.4 (reemplazados por el plan v2 del repo del equipo): proyecto_expediente_vivo.md, arquitectura_detallada.md y sus diagramas (arquitectura_detallada.*, arquitectura_expediente_vivo.*, flujo_conversacion.*), Expediente_Vivo_Propuesta.docx, Analisis_Quejas_y_Flujo.docx (el análisis de datos sigue valiendo; el flujo por tipo es v1.4), propuestas.md.
