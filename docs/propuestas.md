# Propuestas de proyecto: chats que atacan los dolores del contact center

Fecha: 2026-09-26. Basado en docs/hallazgos.md y en una revisión de dolores (analysis: consultas sobre silver).

## Dolores del contact center (con números)

| Dolor | Evidencia |
|---|---|
| Las quejas no se resuelven a la primera | Queja: 56.4% no resuelto (66,000 casos, 60 por día), 431 s por llamada, 377 min de agente al día en llamadas que no resuelven, 63% requiere seguimiento |
| Los reclamos formales se quedan abiertos | 75% abiertos; 20,125 "Open" sin agente asignado ni primera respuesta; 3,321 escalados sin primera respuesta; 20% incumple SLA; 717 vía regulador |
| Esperar | "Tardaron mucho" + "Tuve que esperar" = 25% de los comentarios; 85% de contactos por teléfono con 120 s de espera; digital solo 11% |
| "El agente no fue claro" | 12.6% de los comentarios; en los transcripts el agente responde "{monto} {moneda}" sin el dato |
| Soporte técnico flojo | Técnico: 30% no resuelto, 360 s, 41% seguimiento; 48% de los errores de la app en 3 pantallas (Mis Movimientos, Transferir, Pagar Servicios); "Problema con app" = 20% de reclamos |
| Recontacto | 52% de los contactos son de clientes que llaman 4–6 veces y 31% de los que llaman 7+; 35% queda pendiente de seguimiento |
| Comercial y Retención | 35–40% no resuelto, llamadas más largas (540 s y 478 s) |

Donde el banco ya es bueno: Transaccional (91.5% resuelto, 205 s). Automatizarlo ahorra costo pero no arregla un dolor. El dolor está en Queja y Técnico.

Descartado por ser ruido (probado): priorizar por sentimiento, routing por acento/especialidad, optimización de turnos, predicción de escalamiento, SLA o prioridad.

## Proyecto 1: "Tu queja, bien tomada a la primera" (recomendado)

Ataca: quejas no resueltas, reclamos sin primera respuesta, espera, claridad y recontacto.

El chat:
1. Toma la queja completa a la primera: clasifica en la taxonomía real (cargo no reconocido, cobro indebido, problema con app, atención en sucursal, calidad de servicio), pide solo los datos que faltan (qué cargo, monto, fecha, sucursal) y verifica que sean del cliente contra transacciones y productos reales. Meta: cero "requiere seguimiento" por datos incompletos.
2. Respuesta inmediata con número de caso y fecha realista basada en los tiempos históricos por tipo.
3. Estado sin llamar: "¿cómo va mi reclamo?" en segundos, con lo hecho y lo pendiente.
4. Seguimiento proactivo: aviso al acercarse el SLA, al resolverse, y escalamiento automático si es reincidente, menciona al regulador o superó el SLA sin respuesta.
5. Humano cuando toca: disputa de la resolución, compensación en juego, queja sobre personas de sucursal. Paquete de derivación con hechos verificados, acciones y preguntas abiertas.

Tres casos del brief: normal (queja completa → caso con fecha), ambiguo ("me cobraron de más" → ¿cuál cargo?), humano (reincidente + regulador, o disputa de la resolución).

Qué decide qué:
- Reglas fuera del modelo: propiedad del producto/cargo, campos obligatorios por subcategoría, criterios de escalamiento (reincidente, regulador, SLA vencido, compensación), nunca prometer reembolsos, un caso por cargo.
- Herramientas (gold): perfil, transacciones con fecha local, reclamos del cliente, baseline de tiempos por subcategoría, cola de agentes por idioma y especialidad (7 activos de Quejas hablan portugués: límite a reportar).
- LLM: entender el texto libre en ES/PT y redactar con el registro del país.

Componente aprendido: clasificador de subcategoría + urgencia (regulador, reincidencia) desde texto libre ES/PT, con set generado por el equipo (los transcripts reales son plantillas), contra baseline de palabras clave; held-out por idioma.

Evaluación contra el baseline real (56% no resuelto, 431 s, 0% primera respuesta en Open, 20% SLA): % de quejas tomadas completas sin seguimiento, tiempo a primera respuesta, escalamientos correctos/faltantes/de más, resultados inseguros (mostrar un cargo ajeno: usar las referencias ajenas del dataset como pruebas), latencia p50/p95, costo por caso, desglose ES/PT.

Honestidad para el README: los reclamos del dataset tienen todos más de 500 días al corte (el generador no los avanza) y las encuestas no coinciden con la resolución. Sirven como retrato del dolor, no como historial fiel.

## Proyecto 2: "Soporte técnico que ya sabe qué te pasó"

Ataca: Técnico 30% no resuelto, "Problema con app" 20% de reclamos, claridad.

El chat: al escribir "la app no me deja transferir", el sistema ya vio el error en los eventos digitales (pantalla, versión, plataforma, hora) y guía la solución para esa pantalla y versión (guías sintéticas en RAG); confirma si se resolvió; si no, deriva a Soporte Técnico con el contexto exacto. Ambiguo: "tengo un problema con mi cuenta" → ¿app, pago o cobro? Humano: error repetido tras la guía, o error que afectó dinero (pasa al flujo de reclamo).

Componente aprendido: clasificador problema → pantalla/tipo de error desde texto ES/PT + RAG de guías evaluado con juicios de relevancia. Baseline: 30% no resuelto, 360 s.

Riesgo: los errores digitales no se conectan en el tiempo con las llamadas en este dataset (probado); el "ya vi tu error" se demuestra con un fixture etiquetado.

## Recomendación

Proyecto 1 como proyecto; el 2 como segundo flujo del 1 ("problema con app" es una de sus subcategorías) solo si sobra tiempo.
