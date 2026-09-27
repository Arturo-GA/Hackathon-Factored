# Expediente Vivo: arquitectura detallada y flujo total

Material para la reunión de validación del equipo (27 sep). Diagramas: `arquitectura_detallada.png` (componentes) y `flujo_conversacion.png` (qué pasa en cada turno). Detalle completo en `Expediente_Vivo_Propuesta.docx`.

## 1. La idea en tres frases

1. El cliente escribe (app, WhatsApp o web, en español o portugués) y el sistema construye en vivo un **expediente verificado contra los datos reales del banco**, que el cliente ve y confirma.
2. **Reglas en código** deciden qué pasa con cada mensaje: se resuelve ahora (ruta A), se abre un caso con número y fecha prometida (ruta B) o pasa a una persona con el expediente listo (ruta C). El modelo de lenguaje **nunca decide**: solo entiende texto y redacta respuestas.
3. Un **reloj** vigila las promesas (alerta si nadie asigna el caso en 24 h, avisa al cliente al 80% del plazo, escala si vence) y al cerrar pide una **segunda opinión** al cliente.

## 2. Capas y quién hace qué

| Capa | Componente | Quién lo construye | Qué hace |
|---|---|---|---|
| Canales | Chat del cliente, modo juez, pantalla del agente, tablero del banco, notificaciones simuladas | Arturo + Diego (front) | Puerta de entrada y pantallas para cliente, agente, supervisor y jueces |
| API | FastAPI en App Runner (o Lambda): sesión de prueba, /chat, /tick, trazas | Andrés (infra) + Arturo (endpoints) | Autentica, recibe turnos, corre el reloj, registra todo |
| Orquestador | Máquina de estados: identificar → entender → verificar → decidir → actuar → seguir | Arturo (con Claude Code) | El cerebro determinista; cada paso deja registro de por qué |
| Modelos | Clasificador local (motivo, tipo de queja, urgencia, con probabilidad) y LLM Claude Opus 5 en Bedrock (extraer datos, preguntar, redactar) | Cristhian (clasificador) + Arturo (prompts) | Entienden y redactan; sus salidas son datos que el orquestador usa, nunca órdenes |
| Gateway de herramientas | Único acceso a datos y acciones: alcance por cliente, sin datos personales, auditoría | Andrés | Ninguna consulta ni acción pasa sin verificar que el dato sea del cliente autenticado |
| Herramientas | Buscar cargos, tarjetas, perfil, reclamos, tarifas; abrir/actualizar caso, bloquear tarjeta, enrutar | Diego | Solo lectura más tres acciones, todas verificadas en el core simulado |
| Datos y servicios (AWS) | Gold en S3 (Parquet + DuckDB), casos en DynamoDB, core simulado, colas de agentes, Bedrock, Secrets, CloudWatch | Diego + Andrés | Datos verificados, estado de los casos, acciones simuladas, modelo y observabilidad |
| Datos de origen | Pipeline bronze → silver → gold (ya construido, 194 checks de calidad) | Diego (mantener) | Copia de gold a S3; BigQuery queda como respaldo |
| Evaluación | Conjunto ES/PT, clasificador vs baselines, suite de punta a punta, juez validado | Cristhian | Prueba de que funciona, con números y límites, reproducible con un comando |

## 3. El flujo total, turno a turno

1. **Entra un mensaje.** El cliente ya está autenticado con una sesión de prueba (documento + código de app, 15 minutos). Sin sesión válida no se muestra ningún dato.
2. **Clasificador.** Un modelo pequeño (embeddings multilingües + regresión logística) devuelve motivo (queja, transaccional, producto, técnico, comercial, retención, tarjeta perdida, clave, hablar con persona, emergencia, fuera de alcance), tipo de queja (cargo no reconocido, cobro indebido, app, sucursal, servicio) y señales de urgencia (regulador, compensación, amenaza), cada uno con probabilidad. Tarda 50 ms y no cuesta.
3. **Compuerta de confianza.** ≥ 0,85: sigue. 0,60–0,85: el LLM hace **una** pregunta con las dos opciones más probables como botones. < 0,60 dos veces, "quiero una persona" o emergencia: humano.
4. **Triaje por motivo.** Queja → sigue el flujo. Transaccional o producto → **modo consulta** (saldo, movimientos, estado de un pago, tarjetas) con datos verificados, sin abrir caso; si aparece un cargo no reconocido, entra al flujo de queja. Técnico sin dinero → guía y derivación a Soporte Técnico. Comercial o retención → derivación directa. Fuera de alcance → abstención y menú.
5. **Datos obligatorios por tipo.** El sistema pide solo lo que falta: para un cargo, fecha aproximada, monto o comercio y tarjeta; para un cobro, el cargo y el motivo; para la app, pantalla y fecha; para sucursal, cuál y cuándo; para servicio, canal y fecha. El LLM convierte el texto libre en campos ("450 el 12 de junio en super ahorro" → monto, fecha, comercio) con salida estructurada validada.
6. **Verificar con el gateway.** ¿El cargo existe? ¿Es de un producto del cliente? Estado, código, motivo, riesgo de fraude. ¿El reverso ya se aplicó? ¿El cobro coincide con la tarifa? ¿La sucursal existe? Esto es lo que hoy no ocurre: en la data, el 100% de los reclamos referencia un producto de otro cliente y dos de cada tres no traen monto.
7. **Reglas de ruta (YAML).** Primero los criterios de humano: regulador, reincidente (2+ reclamos reales), prioridad crítica, monto > 500 USD, score de fraude > 30, queja sobre personas, disputa de una resolución → **ruta C** (26% de los casos según la data). Si la evidencia explica el problema (cargo encontrado y coherente, reverso aplicado, cobro igual a tarifa, error de app con guía) → **ruta A**. Si no → **ruta B**.
8. **Redactar.** El LLM escribe la respuesta con los datos ya verificados, en el tono del país (vos/tú) o en portugués. Alrededor del 60% de los turnos (saludos, menús, estado de caso, confirmaciones) va por plantilla, sin modelo.
9. **Acciones con verificación.** Abrir un caso → confirmar que existe. Bloquear una tarjeta → solo con un "sí" explícito del cliente, y se verifica en el core antes de contárselo. El chat nunca desbloquea, nunca promete reembolsos, nunca mueve dinero.
10. **Reloj de promesas.** Cada 15 minutos (acelerable en la demo: 1 día = 1 minuto): 24 h sin asignar → alerta al supervisor; 80% del plazo → aviso al cliente; vencido → escalamiento automático.
11. **Cierre con segunda opinión.** Cuando el humano resuelve, el sistema avisa al cliente y pregunta si quedó conforme. Si no, reabre con prioridad. Todo queda en la traza: qué regla, qué modelo, cuánto tardó, cuánto costó.

**Modo degradado:** si el modelo no responde en 8 segundos, el paso 8 usa plantillas y botones; los pasos 5, 6, 7, 9 y 10 no dependen del modelo. Abrir un caso nunca depende de la IA.

## 4. Qué es humano y qué es automático (resumen)

| Situación | Responde |
|---|---|
| Saludo, menú, estado de caso, número, fecha prometida, avisos del reloj | Automático (plantilla + datos) |
| Entender texto libre, extraer datos, redactar, resumir para el humano | Modelo (Claude), con el clasificador primero |
| Elegir ruta, verificar propiedad, buscar cargo, calcular fecha, abrir caso, escalar | Reglas y herramientas (código) |
| Regulador, reincidente, compensación, riesgo alto, personas, disputa, no verificado, herramienta caída | Humano, con el expediente |

## 5. Lo que los jueces van a poder hacer

- Elegir uno de seis clientes preparados (Lucía, Andrés, Martina, Carlos, João, Sofía), cada uno con una historia distinta, y conversar en español o portugués.
- Crear su propio cliente sintético con transacciones y probar lo que quieran.
- Romper cosas con interruptores: sesión expirada, herramienta caída, modelo lento, pedir datos de otro cliente, inyección de instrucciones.
- Ver en paralelo el chat, el expediente vivo, la pantalla del agente, la traza de cada paso y la pantalla de evaluación (baseline vs sistema por idioma y país).

## 6. Preguntas a resolver en la reunión

1. ¿La cuenta gratuita de AWS permite habilitar Claude en Bedrock y App Runner? Si no: Lambda + API Gateway y API directa de Anthropic.
2. ¿Front en React (más vistoso) o Streamlit (más rápido)? Propuesta: Streamlit si el día 29 el React no está andando.
3. ¿Quién etiqueta el conjunto ES/PT con Cristhian? Se necesitan dos personas y medio día. El portugués se genera y revisa con un LLM externo y se declara como sintético.
4. ¿Se incluye el módulo de notificación por consumo (estilo Yape/BCP) como extensión del día 7, o se deja como trabajo pendiente?
