# Proyecto: "Expediente vivo" — quejas resueltas o encaminadas en una conversación, con evidencia verificada

> **Histórico (v1.4).** Desde el 28 sep manda el plan v2 del repo del equipo (https://github.com/DDR2AS/factored-hackathon-2026-Datti). Qué cambió y qué sigue igual: [alineacion_v2.md](alineacion_v2.md).

## El dolor (con la data)

- Queja: 56% no resuelto al primer contacto, 431 s por llamada, 63% queda "pendiente de seguimiento".
- Reclamo formal: primera respuesta a las 38 h (mediana), 20,125 casos "Open" nunca asignados, 75% abiertos, 16 días de resolución (p90 28), 20% fuera de SLA.
- Los casos se abren incompletos: solo 33% trae monto, 29% sucursal, y el producto referenciado es de otro cliente.
- El cliente: "tardaron mucho" + "tuve que esperar" (25% de comentarios), "no resolvieron mi problema" (13%), "el agente no fue claro" (13%; en los transcripts el agente responde "{monto} {moneda}" sin el dato).
- Recontacto: 29,334 clientes con reclamo formal además llamaron por Queja; 11,179 tienen 2+ reclamos.
- No hay sucursal, país ni subcategoría peor: el dolor es el proceso, no el lugar. Por eso el proyecto ataca el proceso.

## La idea única

No es un chatbot que "toma quejas". Es un **expediente que se construye en vivo, verificado contra los datos del banco, que el cliente ve y confirma, y que es el mismo objeto que recibe el humano**. Tres cosas que hoy no existen en el proceso:

1. **Evidencia verificada en la conversación.** Cada afirmación del cliente se contrasta con datos reales: "me cobraron 450 el 12 de junio" → el sistema encuentra el cargo (o no), confirma que es de su producto, muestra estado y código. Si el dato no existe, lo dice. Nada de abrir casos con producto ajeno.
2. **Tres carriles decididos por reglas, no por el modelo.** (A) se resuelve ahora con datos, (B) caso completo con promesa de fecha y primera respuesta inmediata, (C) humano ahora. El LLM nunca elige el carril.
3. **Promesa con reloj y transparencia.** El cliente ve el expediente ("esto es lo que registramos, ¿está bien?"), recibe número y fecha realista (de la distribución histórica: mediana 16 días, p90 28), y el sistema vigila su propia promesa: primera respuesta en minutos (vs 38 h), aviso a las 24 h si nadie lo asignó, aviso al 80% del SLA, escalamiento automático si vence. El humano recibe el expediente, no un transcript.

## Cuándo LLM, cuándo respuesta automática, cuándo humano

| Situación | Quién responde | Por qué |
|---|---|---|
| Saludo, menú, "¿cómo va mi reclamo?", confirmar número de caso, fecha prometida, recordatorios | **Automático** (plantilla + datos) | Determinista, barato, sin riesgo de inventar. Se estima que cubre ~60% de los turnos |
| Entender la queja en texto libre (ES/PT, dialecto, errores de tipeo), extraer monto/fecha/comercio, redactar la respuesta con el tono del país, resumir el expediente para el humano | **LLM** (con clasificador primero) | Es lenguaje; el LLM solo transforma texto, nunca decide ni calcula |
| Confianza baja del clasificador, o el cliente dice varias cosas a la vez | **LLM pregunta** (una sola pregunta de aclaración) | Caso ambiguo del brief |
| Elegir carril, verificar propiedad, buscar el cargo, calcular fecha, abrir caso, escalar | **Reglas + herramientas** | Política fuera del prompt (exigencia del brief) |
| Mención al regulador, reincidente (2+ reclamos), pide compensación o el monto supera el umbral, queja sobre personas, cliente que disputa la resolución, identidad no verificada, herramienta caída, 3 turnos sin avanzar | **Humano ahora** | Carril C; el LLM solo escribe el resumen del expediente |
| Cliente en portugués que necesita humano | **Humano de Quejas que habla portugués** (7 activos) o especialista con traducción marcada | Límite real de capacidad: se reporta |

## Carriles (máquina de estados)

```
identificar (sesión de prueba) → entender (clasificador → LLM si duda) → verificar evidencia (tools)
   ├─ A: se explica con datos (cargo encontrado y coherente, reverso ya aplicado, error de app conocido, cobro = tarifa publicada)
   │      → respuesta con el dato exacto → "¿quedó resuelto?" → sí: cierre / no: pasa a B
   ├─ B: evidencia completa pero requiere gestión → caso con expediente, número, fecha prometida, primera respuesta inmediata
   │      → seguimiento proactivo (24 h sin asignar → alerta; 80% SLA → aviso; vencido → escalar)
   └─ C: regla de derivación disparada → paquete al humano + cliente informado de quién y cuándo
```

Reglas de completitud por subcategoría (para que ningún caso nazca incompleto): cargo no reconocido → transacción identificada y propia; cobro indebido → cargo + motivo; problema con app → pantalla + fecha (+ evento de error si existe); atención en sucursal → sucursal + fecha; calidad de servicio → canal + fecha (+ contacto previo si existe).

## Herramientas (leen gold y un core simulado)

- `get_customer_context` (customer_profile): segmento, reclamos abiertos, contactos recientes, reincidencia.
- `find_transactions` (transactions_enriched): por fecha local, monto aproximado, comercio; solo del cliente autenticado.
- `get_product` / `get_cards` (customer_cards).
- `get_app_errors` (digital_events del cliente: pantalla, versión, hora).
- `complaint_stats` (complaints_baseline): mediana y p90 por subcategoría para la promesa.
- `open_case`, `update_case`, `get_case_status`, `escalate` (servicio de casos simulado, con estados y SLA).
- `route_to_agent` (agents_routing): idioma, especialidad, disponibilidad.
- Todo con verificación de propiedad y registro de auditoría; las acciones devuelven un resultado que se muestra solo si el core lo confirmó.

## Componente aprendido (vs baseline)

Clasificador de intención + subcategoría + señales de urgencia (regulador, reincidencia, compensación) sobre texto libre en ES y PT.
- Datos: los transcripts reales no sirven (son plantillas). Set generado por el equipo: ~600–1,000 frases con variantes por país (vos/tú, léxico), portugués, errores de tipeo y casos adversarios; etiquetado a mano por dos personas; split estratificado por idioma; sin fuga (variantes de una misma frase en el mismo split).
- Modelos: baseline de palabras clave → embeddings multilingües + regresión logística → LLM zero-shot. Métricas: F1 por clase e idioma, y **tasa de "pregunta de aclaración"** según el umbral de confianza (es la palanca LLM vs automático).

## Evaluación (contra el baseline real de la data)

| Métrica | Baseline (data) | Cómo se mide en el sistema |
|---|---|---|
| Primera respuesta con número de caso | 38 h (mediana), 100% de los Open sin respuesta | segundos, en 100% de los casos B |
| Casos abiertos completos | 33% con monto, 29% con sucursal, producto ajeno | % de casos con los campos obligatorios y evidencia propia |
| Resolución segura en el contacto (carril A) | 43.6% resuelto en Queja | % de casos de prueba de carril A cerrados correctamente |
| Derivaciones | — | correctas / faltantes / de más contra etiquetas |
| Resultados inseguros | — | mostrar o registrar un cargo de otro cliente (pruebas con las referencias ajenas del dataset), actuar ante inyección, sesión expirada |
| Latencia y costo | 431 s por llamada; 11 h-agente/día en quejas | p50/p95 por turno; costo LLM por caso; % de turnos sin LLM |
| Por idioma y país | — | todas las anteriores desglosadas ES/PT y MX/CO/AR |

Suite: 200+ conversaciones sintéticas etiquetadas (ES/PT balanceadas, 15% adversarias). Juez LLM solo para calidad de redacción, validado con una muestra humana.

## Demo funcional (9 días)

Pantallas: (1) chat del cliente estilo WhatsApp con selector ES/PT y de usuario de prueba, (2) panel del **expediente vivo** que se llena mientras conversa, (3) consola del agente humano con cola por carril/idioma y el expediente, (4) panel de operación: carriles, promesas en riesgo, métricas de evaluación y trazas.

| Día | Entrega |
|---|---|
| 1 | Máquina de estados, reglas de carril y completitud, esquema del expediente, diseño del set ES/PT |
| 2 | Servicio de casos simulado (estados, SLA, reloj), herramientas sobre gold, capa de permisos/propiedad |
| 3 | Backend conversacional: clasificador provisional + LLM, plantillas automáticas, trazas |
| 4 | Chat + expediente vivo (UI); flujo carril A y B de punta a punta |
| 5 | Carril C + consola del agente + routing por idioma; seguimiento proactivo (reloj) |
| 6 | Set ES/PT etiquetado, clasificador final vs baselines, umbral de confianza |
| 7 | Suite de evaluación, adversarios, métricas, desgloses; corrección de fallos |
| 8 | Deploy, README con guía de prueba y usuarios sintéticos, prueba de actualización de datos |
| 9 | Video, slides, limitaciones (transcripts sintéticos, PT sin datos, 7 agentes PT, reclamos estáticos) |

## Riesgos y límites que se declaran

- Los reclamos del dataset no avanzan en el tiempo y los transcripts son plantillas: el ciclo de vida se simula y se etiqueta como tal.
- Los eventos digitales no se conectan con las llamadas: el "ya vi tu error" funciona con fixture.
- Portugués: sin datos reales; 7 agentes de Quejas lo hablan.
- No se prometen reembolsos ni compensaciones: solo se registran y derivan.
