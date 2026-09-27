# -*- coding: utf-8 -*-
"""Genera docs/arquitectura_detallada.svg/png y docs/flujo_conversacion.svg/png (sin dependencias externas)."""
import math, pymupdf
from html import escape as E

OUT = r"C:\Users\Arturo\Documents\Factored Hackathon\docs\\"
G = ("#F1EFE8", "#888780", "#2C2C2A", "#5F5E5A")   # gris: canales/herramientas/datos
P = ("#EEEDFE", "#534AB7", "#26215C", "#534AB7")   # morado: decide (código)
C = ("#FAECE7", "#D85A30", "#4A1B0C", "#993C1D")   # coral: modelos
T = ("#E1F5EE", "#1D9E75", "#04342C", "#0F6E56")   # verde: humano
B = ("#E6F1FB", "#378ADD", "#042C53", "#185FA5")   # azul: AWS (contenedor)


class SVG:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Arial, Helvetica, sans-serif">',
                      f'<rect x="0" y="0" width="{w}" height="{h}" fill="#ffffff"/>']

    def box(self, x, y, w, h, pal, title, lines=(), tsize=14, lsize=11, dashed=False, num=None):
        f, s, tc, sc = pal
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{f}" stroke="{s}" stroke-width="1.2"{dash}/>')
        cy = y + 20
        if num is not None:
            self.parts.append(f'<circle cx="{x+14}" cy="{y+14}" r="10" fill="{s}"/><text x="{x+14}" y="{y+18}" font-size="11" font-weight="bold" fill="#ffffff" text-anchor="middle">{num}</text>')
        self.parts.append(f'<text x="{x+w/2}" y="{cy}" font-size="{tsize}" font-weight="bold" fill="{tc}" text-anchor="middle">{E(title)}</text>')
        for i, ln in enumerate(lines):
            self.parts.append(f'<text x="{x+w/2}" y="{cy+17+i*14}" font-size="{lsize}" fill="{sc}" text-anchor="middle">{E(ln)}</text>')

    def region(self, x, y, w, h, label, color="#888780"):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="none" stroke="{color}" stroke-width="1" stroke-dasharray="5 4"/>')
        self.parts.append(f'<text x="{x+10}" y="{y+16}" font-size="11" font-weight="bold" fill="{color}">{E(label)}</text>')

    def arrow(self, pts, color="#5F5E5A", label=None, dashed=False, width=1.6):
        d = " ".join(f"{px},{py}" for px, py in pts)
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        self.parts.append(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{width}"{dash}/>')
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        ang = math.atan2(y2 - y1, x2 - x1); L = 9
        p1 = (x2 - L * math.cos(ang - 0.45), y2 - L * math.sin(ang - 0.45))
        p2 = (x2 - L * math.cos(ang + 0.45), y2 - L * math.sin(ang + 0.45))
        self.parts.append(f'<polygon points="{x2},{y2} {p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}" fill="{color}"/>')
        if label:
            mx, my = pts[len(pts)//2] if len(pts) > 2 else ((x1+x2)/2, (y1+y2)/2)
            self.parts.append(f'<rect x="{mx-len(label)*3.2-4}" y="{my-9}" width="{len(label)*6.4+8}" height="15" fill="#ffffff"/>')
            self.parts.append(f'<text x="{mx}" y="{my+3}" font-size="10.5" fill="{color}" text-anchor="middle">{E(label)}</text>')

    def text(self, x, y, t, size=12, color="#2C2C2A", bold=False, anchor="start"):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}"{" font-weight=\"bold\"" if bold else ""}>{E(t)}</text>')

    def save(self, name):
        svg = "\n".join(self.parts + ["</svg>"])
        open(OUT + name + ".svg", "w", encoding="utf-8").write(svg)
        pymupdf.open(stream=svg.encode("utf-8"), filetype="svg")[0].get_pixmap(dpi=170).save(OUT + name + ".png")
        print("ok", name)


# =====================================================================
# DIAGRAMA 1: ARQUITECTURA DETALLADA
# =====================================================================
d = SVG(1500, 1040)
d.text(30, 34, "Expediente Vivo · Arquitectura detallada (los números siguen el camino de una queja)", 19, bold=True)

# --- Canales (cliente y banco)
d.region(30, 55, 1440, 110, "CANALES  ·  quién usa el sistema")
d.box(50, 80, 250, 70, G, "Cliente · chat", ["app / WhatsApp / web (simulados)", "español y portugués · botones y texto libre"], num=1)
d.box(330, 80, 250, 70, G, "Modo juez", ["6 clientes preparados · crear cliente", "interruptores de falla · reiniciar demo"])
d.box(610, 80, 250, 70, T, "Pantalla del agente humano", ["cola por ruta e idioma · expediente", "tomar · resolver · devolver"], num=10)
d.box(890, 80, 250, 70, G, "Tablero del banco", ["rutas, promesas en riesgo, métricas", "por tipo, canal, idioma y país"])
d.box(1170, 80, 280, 70, G, "Notificaciones (simuladas)", ["push / correo por consumo y por caso", "botón: 'no reconozco este consumo'"])

# --- API + sesión
d.region(30, 185, 1440, 95, "API  ·  FastAPI en AWS App Runner (o Lambda)")
d.box(50, 210, 330, 55, G, "Sesión y autenticación de prueba", ["documento + código de app → sesión 15 min", "sin sesión válida no se muestra nada"], num=2)
d.box(410, 210, 330, 55, G, "Endpoint /chat", ["recibe el turno, devuelve respuesta + expediente", "límite de mensajes por sesión"])
d.box(770, 210, 330, 55, G, "Endpoint /tick (reloj)", ["EventBridge cada 15 min (acelerable en demo)", "alertas 24 h · 80% SLA · vencido · 2ª opinión"], num=9)
d.box(1130, 210, 320, 55, G, "Trazas y auditoría", ["cada regla, herramienta y consulta al modelo", "tiempo, costo, versión → CloudWatch + S3"])

# --- Orquestador
d.region(30, 300, 1440, 130, "ORQUESTADOR  ·  código Python: máquina de estados; el modelo nunca decide", "#534AB7")
d.box(50, 330, 200, 80, P, "Identificar", ["carga perfil del cliente", "(sin datos personales)"], num=2)
d.box(280, 330, 200, 80, P, "Entender", ["triaje del motivo", "→ tipo de queja → urgencia"], num=3)
d.box(510, 330, 200, 80, P, "Verificar", ["pide solo lo obligatorio", "busca el cargo · ¿es suyo?"], num=5)
d.box(740, 330, 200, 80, P, "Decidir", ["reglas YAML → ruta A / B / C", "registra por qué"], num=6)
d.box(970, 330, 200, 80, P, "Actuar", ["responder · abrir caso", "bloquear (con confirmación)"], num=7)
d.box(1200, 330, 250, 80, P, "Seguir", ["promesa con fecha · reloj", "segunda opinión al cerrar"], num=8)
for x in (250, 480, 710, 940, 1170):
    d.arrow([(x, 370), (x + 30, 370)], "#534AB7")

# --- Modelos
d.region(30, 450, 700, 130, "MODELOS  ·  entienden y redactan; sus salidas son datos, no órdenes", "#D85A30")
d.box(50, 480, 320, 85, C, "Clasificador local (Cristhian)", ["embeddings multilingües + regresión logística", "motivo (6+) · tipo de queja (5) · urgencia", "50 ms · costo 0 · devuelve probabilidad"], num=4)
d.box(400, 480, 310, 85, C, "LLM · Claude Opus 5 (Bedrock)", ["extrae monto, fecha, comercio (salida estructurada)", "hace UNA pregunta si la confianza es media", "redacta en ES/PT con el tono del país · resume"], num=4)
d.arrow([(380, 340), (210, 480)], "#D85A30", "texto del cliente")
d.arrow([(400, 340), (555, 480)], "#D85A30", "solo si hace falta")
d.arrow([(1070, 410), (1070, 445), (720, 445), (720, 522), (712, 522)], "#D85A30", "redactar respuesta")

# --- Gateway + herramientas
d.region(760, 450, 710, 130, "GATEWAY DE HERRAMIENTAS  ·  único acceso a datos y acciones", "#534AB7")
d.box(780, 480, 330, 85, P, "Gateway", ["alcance = solo el cliente autenticado", "sin nombres, documentos ni contactos", "cada llamada queda registrada"], num=5)
d.box(1130, 480, 320, 85, G, "Herramientas (solo lectura + 3 acciones)", ["buscar cargos · tarjetas · perfil · reclamos", "abrir/actualizar caso · bloquear tarjeta", "enrutar a cola de agentes · tarifas"])
d.arrow([(610, 410), (610, 440), (945, 440), (945, 480)], "#534AB7", "consultar / actuar")
d.arrow([(1110, 522), (1130, 522)], "#534AB7")

# --- Datos y servicios
d.region(30, 600, 1440, 120, "DATOS Y SERVICIOS  ·  AWS", "#378ADD")
d.box(50, 628, 260, 78, B, "Gold en S3 (Parquet + DuckDB)", ["customer_profile · transactions_enriched", "customer_cards · complaints_baseline", "agents_routing · tarifas sintéticas"])
d.box(340, 628, 260, 78, B, "Servicio de casos · DynamoDB", ["expedientes, estados, promesas, reloj", "clientes sintéticos de la demo", "nunca escribe en las tablas gold"])
d.box(630, 628, 260, 78, B, "Core bancario simulado", ["bloqueo de tarjeta con verificación", "devuelve resultado real o error", "sin dinero real"])
d.box(920, 628, 260, 78, B, "Colas de agentes", ["Quejas y Reclamos (64) · Fraudes (96)", "Soporte Técnico (89) · Ventas (74)", "Retención (85) · portugués (7 en Quejas)"])
d.box(1210, 628, 240, 78, B, "Bedrock · Secrets · CloudWatch", ["modelo con permisos IAM", "presupuesto 30 USD con alarma", "logs y métricas"])
for x in (180, 470, 760, 1050):
    d.arrow([(1290, 565), (1290, 590), (x, 590), (x, 628)], "#5F5E5A")
d.arrow([(1290, 565), (1330, 628)], "#5F5E5A")

# --- Pipeline y evaluación (offline)
d.region(30, 740, 700, 130, "DATOS DE ORIGEN  ·  pipeline ya construido", "#5F5E5A")
d.box(50, 768, 200, 85, G, "S3 del hackathon", ["13 tablas CSV diarias", "extract incremental"])
d.box(280, 768, 200, 85, G, "bronze → silver → gold", ["contratos (194 checks)", "DuckDB · reproducible"])
d.box(510, 768, 200, 85, G, "Copia a S3 (Parquet)", ["BigQuery queda como respaldo", "fixture de actualización"])
d.arrow([(250, 810), (280, 810)]); d.arrow([(480, 810), (510, 810)])
d.arrow([(610, 768), (610, 730), (180, 730), (180, 706)], "#5F5E5A", dashed=True)

d.region(760, 740, 710, 130, "EVALUACIÓN  ·  offline, reproducible con un comando", "#D85A30")
d.box(780, 768, 220, 85, C, "Conjunto ES/PT (equipo)", ["600–1.000 frases etiquetadas", "200+ conversaciones con resultado", "15% adversarias · sintético declarado"])
d.box(1020, 768, 210, 85, C, "Clasificador vs baselines", ["palabras clave · LLM zero-shot", "F1 por clase e idioma", "umbral del score de fraude"])
d.box(1250, 768, 200, 85, C, "Suite de punta a punta", ["resolución segura · inseguros", "derivaciones · latencia · costo", "juez validado con humanos"])
d.arrow([(1000, 810), (1020, 810)], "#D85A30"); d.arrow([(1230, 810), (1250, 810)], "#D85A30")

# --- Flechas principales
d.arrow([(175, 150), (175, 210)], label="turno")
d.arrow([(455, 150), (455, 210)])
d.arrow([(735, 150), (735, 210)], "#1D9E75", "toma el caso")
d.arrow([(1015, 150), (1015, 210)])
d.arrow([(1310, 150), (1310, 210)])
d.arrow([(575, 265), (575, 300)], "#534AB7", "cada turno")
d.arrow([(935, 265), (935, 300)], "#534AB7", "reloj")

# leyenda
lx = 30; ly = 900
for pal, lab in ((P, "decide (código, auditable)"), (C, "modelos: entienden y redactan"), (G, "canales, herramientas y datos"), (B, "servicios AWS"), (T, "humano")):
    d.parts.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" rx="3" fill="{pal[0]}" stroke="{pal[1]}"/>')
    d.text(lx + 20, ly + 12, lab, 12); lx += 260
d.text(30, 940, "Camino de una queja: 1 el cliente escribe → 2 sesión y perfil → 3 el clasificador dice motivo, tipo y urgencia → 4 el LLM extrae datos o pregunta → 5 el gateway busca el cargo y verifica que sea del cliente →", 11.5, "#5F5E5A")
d.text(30, 958, "6 las reglas eligen la ruta (A resolver / B caso con promesa / C humano) → 7 se actúa y se verifica en el core → 8 promesa con fecha y reloj → 9 el reloj avisa y escala → 10 el humano recibe el expediente, no un transcript.", 11.5, "#5F5E5A")
d.text(30, 990, "Modo degradado: si el modelo no responde, los pasos 2, 5, 6, 7 y 8 siguen funcionando con plantillas y botones; abrir un caso nunca depende del LLM.", 11.5, "#993C1D")
d.save("arquitectura_detallada")

# =====================================================================
# DIAGRAMA 2: FLUJO DE UNA CONVERSACIÓN
# =====================================================================
f = SVG(1500, 1010)
f.text(30, 34, "Expediente Vivo · Flujo de una conversación (qué decide cada paso y quién lo hace)", 19, bold=True)
f.text(30, 56, "Colores: morado = regla en código · coral = modelo · verde = humano · gris = automático con datos", 12, "#5F5E5A")

# fila 1: entrada y triaje
f.box(40, 90, 220, 70, G, "1 · Entra un mensaje", ["cliente autenticado (sesión de prueba)", "canal: app / WhatsApp / web"])
f.arrow([(260, 125), (300, 125)])
f.box(300, 90, 260, 70, C, "2 · Clasificador", ["motivo + tipo de queja + urgencia", "con probabilidad"])
f.arrow([(560, 125), (600, 125)])
f.box(600, 90, 250, 70, P, "3 · Compuerta de confianza", ["≥ 0,85 sigue · 0,60–0,85 aclara", "< 0,60 dos veces → humano"])
f.arrow([(850, 110), (930, 110)], "#D85A30", "0,60–0,85")
f.box(930, 80, 230, 60, C, "LLM pregunta (una vez)", ["'¿fue un cargo o la app?'", "con 2 opciones como botones"])
f.arrow([(1045, 140), (1045, 175), (725, 175), (725, 160)], "#D85A30", "respuesta del cliente")
f.arrow([(850, 140), (880, 140), (880, 215), (1230, 215), (1230, 250)], "#534AB7", "< 0,60 ×2 · 'quiero una persona' · emergencia")

# fila 2: triaje por motivo
f.box(40, 250, 300, 110, P, "4 · Triaje por motivo", ["Queja → sigue abajo", "Transaccional / Producto → modo consulta", "Técnico sin dinero → guía + derivación", "Comercial / Retención → derivación directa", "fuera de alcance → abstención + menú"])
f.arrow([(725, 160), (725, 220), (190, 220), (190, 250)], "#534AB7")
f.box(40, 400, 300, 100, G, "Modo consulta (sin caso)", ["saldo, movimientos, estado de un pago,", "tarjetas y vencimiento: datos verificados", "por el gateway; si aparece un cargo", "no reconocido → entra al flujo de queja"])
f.arrow([(190, 360), (190, 400)], "#5F5E5A", "Transaccional / Producto")
f.box(720, 250, 300, 110, P, "5 · Datos obligatorios por tipo", ["cargo: fecha, monto o comercio + tarjeta", "cobro: cargo + motivo", "app: pantalla + fecha", "sucursal: sucursal + fecha + qué pasó", "servicio: canal + fecha + qué pasó"])
f.arrow([(340, 305), (720, 305)], "#534AB7", "Queja (5 tipos)")
f.box(1060, 250, 400, 110, T, "Humano ahora (ruta C)", ["paquete de derivación: hechos verificados,", "acciones, evidencia, preguntas abiertas", "cola por especialidad e idioma (7 con portugués)", "SLA interno: 2 h fraude · 4 h regulador · 8 h reincidente"])

# fila 3: verificar
f.box(720, 400, 300, 100, P, "6 · Verificar con el gateway", ["¿el cargo existe? ¿es de un producto del cliente?", "estado, código, motivo, riesgo de fraude", "¿reverso ya aplicado? ¿coincide con tarifa?", "¿la sucursal existe? ¿hubo contacto ese día?"])
f.arrow([(870, 360), (870, 400)], "#534AB7", "pide solo lo que falta")
f.box(380, 400, 300, 100, C, "LLM extrae entidades", ["'450 el 12 de junio en super ahorro' →", "{monto: 450, fecha: 2026-06-12, comercio: ...}", "salida estructurada validada"])
f.arrow([(720, 430), (680, 430)], "#D85A30", "texto libre")
f.arrow([(680, 470), (720, 470)], "#D85A30", "campos")

# fila 4: decidir
f.box(720, 540, 300, 110, P, "7 · Reglas de ruta (YAML)", ["¿regulador, reincidente, crítico, > 500 USD,", "score > 30, personas, disputa? → C", "¿la evidencia explica el problema? → A", "si no → B"])
f.arrow([(870, 500), (870, 540)], "#534AB7")
f.arrow([(1020, 595), (1260, 595), (1260, 360)], "#1D9E75", "C")
f.box(40, 540, 300, 110, G, "Ruta A · se resuelve ahora", ["respuesta con el dato exacto: cargo,", "comercio, fecha local, estado, motivo", "'¿quedó resuelto?' → sí: cierre", "no → pasa a B"])
f.arrow([(720, 570), (340, 570)], "#5F5E5A", "A")
f.box(380, 540, 300, 110, G, "Ruta B · caso con promesa", ["expediente completo y verificado", "número de caso + fecha (90% ≤ 28 días)", "primera respuesta en segundos", "el cliente ve y confirma el expediente"])
f.arrow([(720, 620), (680, 620)], "#5F5E5A", "B")
f.arrow([(120, 650), (120, 680), (420, 680), (420, 650)], "#5F5E5A", "no quedó resuelto")

# fila 5: actuar / seguir
f.box(40, 730, 300, 100, C, "8 · LLM redacta (o plantilla)", ["tono del país (vos/tú), portugués", "solo con datos ya verificados", "~60% de los turnos van por plantilla"])
f.arrow([(260, 650), (260, 730)], "#D85A30")
f.box(380, 730, 300, 100, P, "9 · Acciones con verificación", ["abrir caso → confirmar que existe", "bloquear tarjeta → solo con 'sí' explícito", "→ verificar en el core antes de contarlo"])
f.arrow([(600, 650), (600, 730)], "#534AB7")
f.box(720, 730, 300, 100, P, "10 · Reloj de promesas", ["24 h sin asignar → alerta al supervisor", "80% del plazo → aviso al cliente", "vencido → escala solo"])
f.arrow([(680, 780), (720, 780)], "#534AB7")
f.box(1060, 730, 400, 100, T, "11 · Cierre con segunda opinión", ["el humano resuelve → el sistema avisa al cliente", "'¿quedó conforme?' → no: reabre con prioridad", "todo queda en la traza: regla, modelo, tiempo, costo"])
f.arrow([(1020, 780), (1060, 780)], "#534AB7")
f.arrow([(1260, 360), (1260, 730)], "#1D9E75", "resolución humana", dashed=True)

f.text(30, 880, "Ejemplo (Lucía, ES): 'me cobraron 450 el 12 de junio y no fui yo' → clasificador: Queja / cargo no reconocido / sin urgencia (0,93) → LLM extrae {450, 2026-06-12}", 11.5, "#5F5E5A")
f.text(30, 898, "→ gateway encuentra el cargo en su tarjeta 4821, aprobado, comercio 'Super Ahorro', riesgo bajo → reglas: no hay criterio C; la evidencia explica el cargo → ruta A: se le muestra el detalle;", 11.5, "#5F5E5A")
f.text(30, 916, "'ah sí, fue en el supermercado' → cierre. Si dice 'no fui yo' → ruta B: caso con número y fecha; si el score fuera > 30 → ruta C: ofrece bloqueo con confirmación y va a Fraudes.", 11.5, "#5F5E5A")
f.text(30, 950, "Ejemplo (João, PT): 'não reconheço uma compra' → mismo flujo; si necesita humano, se enruta a uno de los 7 agentes de Quejas que hablan portugués; la respuesta se redacta en portugués.", 11.5, "#5F5E5A")
f.text(30, 984, "Modo degradado: si el LLM no responde en 8 s, el paso 8 usa plantillas y botones; los pasos 5, 6, 7, 9 y 10 no dependen del modelo.", 11.5, "#993C1D")
f.save("flujo_conversacion")
