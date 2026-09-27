# -*- coding: utf-8 -*-
"""Genera docs/Analisis_Quejas_y_Flujo_v2.docx"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = r"C:\Users\Arturo\Documents\Factored Hackathon\docs\Analisis_Quejas_y_Flujo_v2.docx"
AZUL = RGBColor(0x1F, 0x3A, 0x5F); GRIS = RGBColor(0x59, 0x59, 0x59)
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.2); sec.top_margin = sec.bottom_margin = Cm(2.0)
n = doc.styles["Normal"]; n.font.name = "Calibri"; n.font.size = Pt(10.5)
n.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri"); n.paragraph_format.space_after = Pt(6)
for lvl, size in ((1, 17), (2, 13.5), (3, 11.5)):
    st = doc.styles[f"Heading {lvl}"]; st.font.name = "Calibri"; st.font.size = Pt(size); st.font.bold = True
    st.font.color.rgb = AZUL; st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    st.paragraph_format.space_before = Pt(12); st.paragraph_format.space_after = Pt(4)
fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = fp.add_run("Análisis de quejas y flujo de atención · Expediente Vivo · página "); r.font.size = Pt(8); r.font.color.rgb = GRIS
for tag, txt in (("begin", None), (None, "PAGE"), ("end", None)):
    run = fp.add_run(); run.font.size = Pt(8); run.font.color.rgb = GRIS
    if tag:
        fc = OxmlElement("w:fldChar"); fc.set(qn("w:fldCharType"), tag); run._r.append(fc)
    else:
        it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = txt; run._r.append(it)


def shade(el, fill):
    pr = el._tc.get_or_add_tcPr() if hasattr(el, "_tc") else el._p.get_or_add_pPr()
    s = OxmlElement("w:shd"); s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), fill); pr.append(s)


def h(t, l=1): return doc.add_heading(t, l)


def p(t="", bold=False, italic=False, size=None, color=None, align=None, after=None):
    par = doc.add_paragraph(); run = par.add_run(t); run.bold, run.italic = bold, italic
    if size: run.font.size = Pt(size)
    if color: run.font.color.rgb = color
    if align: par.alignment = align
    if after is not None: par.paragraph_format.space_after = Pt(after)
    return par


def rich(parts, style=None):
    par = doc.add_paragraph(style=style) if style else doc.add_paragraph()
    for part in parts:
        if isinstance(part, str): par.add_run(part)
        else:
            run = par.add_run(part[0]); run.bold = "b" in part[1]; run.italic = "i" in part[1]
    return par


def bullet(parts):
    par = rich(parts if isinstance(parts, list) else [parts], style="List Bullet"); par.paragraph_format.space_after = Pt(2); return par


def num(parts):
    par = rich(parts if isinstance(parts, list) else [parts], style="List Number"); par.paragraph_format.space_after = Pt(2); return par


def note(t, label="Nota"):
    par = doc.add_paragraph(); shade(par, "F2F2F2"); par.paragraph_format.left_indent = Cm(0.3); par.paragraph_format.space_after = Pt(8)
    r1 = par.add_run(f"{label}: "); r1.bold = True; r1.font.size = Pt(9.5)
    r2 = par.add_run(t); r2.italic = True; r2.font.size = Pt(9.5)


def table(headers, rows, widths, size=9, bold_first=False, bold_last=False):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    for i, hd in enumerate(headers):
        c = t.rows[0].cells[i]; c.width = Cm(widths[i]); c.text = ""
        run = c.paragraphs[0].add_run(hd); run.bold = True; run.font.size = Pt(size); shade(c, "D9E2F3")
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].width = Cm(widths[i]); cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(val)); run.font.size = Pt(size)
            if (bold_first and i == 0) or (bold_last and ri == len(rows) - 1): run.bold = True
    for row in t.rows:
        for c in row.cells:
            for par in c.paragraphs: par.paragraph_format.space_after = Pt(1)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def pb(): doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def f(x): return f"{x:,}".replace(",", ".")


# ---------------- PORTADA ----------------
for _ in range(7): doc.add_paragraph()
p("Análisis de quejas y flujo de atención", bold=True, size=26, color=AZUL, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
p("Clasificación completa de los reclamos del dataset LATAM Bank y ruta que sigue cada uno en Expediente Vivo", size=13, color=GRIS, align=WD_ALIGN_PARAGRAPH.CENTER, after=30)
p("Factored AI & Data Hackathon 2026 · 27 de septiembre de 2026 · Borrador para el equipo", size=11, color=GRIS, align=WD_ALIGN_PARAGRAPH.CENTER, after=30)
p("Todas las cifras se calcularon sobre la población completa del dataset (117.021 contactos de queja, 67.095 casos formales, 4.425.008 transacciones). No se usaron muestras.", size=10.5, align=WD_ALIGN_PARAGRAPH.CENTER, after=24)
for t in ["1. Una queja es un solo viaje con dos momentos", "2. Los cinco tipos de queja: volumen, qué piden, con qué evidencia llegan, qué pasa hoy", "3. Cómo se trata cada tipo: flujo general, ruta por tipo, volúmenes por ruta, vía rápida de fraude", "4. Contactos que no son quejas: qué hace el sistema con ellos"]:
    p(t, size=10.5, after=1)
pb()

# ---------------- 1. UN SOLO VIAJE ----------------
h("1. Una queja es un solo viaje con dos momentos")
p("El dataset registra la queja en dos tablas distintas, pero son dos momentos del mismo viaje del cliente. Todo el documento se organiza sobre esta línea:")
table(["", "Momento 1 · El cliente se queja", "Momento 2 · Se abre un caso formal"], [
    ["Tabla", "call_center_interactions (motivo = Queja)", "complaints (sistema PQR)"],
    ["Volumen (3 años)", "117.021 contactos", "67.095 casos"],
    ["Por año / por día hábil", "39.007 / 124", "22.365 / 61"],
    ["Por dónde", "85% teléfono, 4% email, 3,8% app, 3,4% web chat, 3,3% WhatsApp", "50% desde el call center; 20% email, 15% web, 10% app, 4% sucursal, 1% regulador (estos entran sin pasar por el momento 1)"],
    ["Qué pasa", "43,6% se resuelve ahí mismo; 56,4% no; 63% queda 'pendiente de seguimiento'; dura 431 s", "Asignación a las 12 h; primera respuesta a las 38 h; 30% nunca asignado; 16 días de resolución (28 en el 90% de los casos); 20% fuera de plazo"],
    ["Qué sabe el banco del motivo", "Nada: el sistema anota solo 'Queja'", "La subcategoría (5 tipos) y lo que pide el cliente (4 tipos de caso)"],
    ["Lo que el cliente dice después", "'Tardaron mucho', 'no resolvieron mi problema', 'no fue claro' (CSAT 2,43)", "Satisfacción con la resolución 3,0/5; 11.179 clientes reclaman 2 o más veces"],
], [3.2, 6.4, 6.9], size=8.5, bold_first=True)
rich(["Conexión entre los dos momentos: 33.761 casos formales entraron por el call center, es decir, aproximadamente ", ("3 de cada 10 contactos de queja terminan en un caso formal", "b"),
      " (el dataset no enlaza cada caso con su llamada, así que es una proporción de volúmenes). 29.334 clientes aparecen en los dos momentos."])
pb()

# ---------------- 2. LOS CINCO TIPOS ----------------
h("2. Los cinco tipos de queja")
p("La clasificación por motivo existe en el momento 2 (subcategoría del caso). En el momento 1 el banco no la registra, así que se estima con la misma mezcla; el clasificador del sistema es el que la producirá en adelante.")
table(["Tipo de queja", "Casos formales (3 años)", "%", "Contactos estimados por día hábil*", "Qué reclama el cliente"], [
    ["Cargo no reconocido", "13.580", "20,2%", "≈ 25", "Un consumo o movimiento que no hizo (posible fraude, compra olvidada, comercio con otro nombre, cargo pendiente)"],
    ["Cobro indebido", "13.553", "20,2%", "≈ 25", "Una comisión o cobro que considera incorrecto (duplicado, tarifa no informada, monto distinto)"],
    ["Problema con app", "13.407", "20,0%", "≈ 25", "La app o la web no le permite operar, o le dio error"],
    ["Atención en sucursal", "13.361", "19,9%", "≈ 25", "Mal trato, demora o error en una sucursal"],
    ["Calidad de servicio", "13.194", "19,7%", "≈ 25", "Mal servicio en cualquier canal (call center, email, chat)"],
    ["Total", "67.095", "100%", "124", ""],
], [3.2, 2.4, 1.3, 2.8, 6.8], size=8.5, bold_first=True, bold_last=True)
note("*Supuesto: los 124 contactos diarios de queja siguen la misma mezcla que los casos formales (el 50% de los casos nace en el call center y las cinco subcategorías pesan igual). Se declara como estimación.", "Supuesto")

h("2.1 Cada tipo, según lo que pide el cliente (tipo de caso)", 2)
p("Dentro de cada tipo, el sistema PQR distingue qué pide el cliente. Esto sí cambia el tratamiento: una sugerencia no se investiga; un reclamo con dinero sí.")
table(["Tipo de queja", "Queja (inconformidad)", "Reclamo con dinero", "Solicitud", "Sugerencia", "Total"], [
    ["Cargo no reconocido", "8.239", "3.335", "1.329", "677", "13.580"],
    ["Cobro indebido", "8.171", "3.357", "1.367", "658", "13.553"],
    ["Problema con app", "8.120", "3.312", "1.335", "640", "13.407"],
    ["Atención en sucursal", "7.969", "3.355", "1.372", "665", "13.361"],
    ["Calidad de servicio", "7.953", "3.239", "1.358", "644", "13.194"],
    ["Total", "40.452 (60%)", "16.598 (25%)", "6.761 (10%)", "3.284 (5%)", "67.095"],
], [3.4, 2.8, 2.6, 2.2, 2.2, 2.0], bold_first=True, bold_last=True)

h("2.2 Cómo llega cada tipo y qué evidencia trae", 2)
table(["Tipo de queja", "Trae monto", "Trae producto", "…y es de otro cliente", "Trae sucursal", "Texto libre"], [
    ["Cargo no reconocido", "4.500 (33%)", "9.001 (66%)", "100%", "3.904 (29%)", "No (plantilla)"],
    ["Cobro indebido", "4.457 (33%)", "9.019 (67%)", "100%", "3.918 (29%)", "No (plantilla)"],
    ["Problema con app", "4.352 (32%)", "8.905 (66%)", "100%", "3.802 (28%)", "No (plantilla)"],
    ["Atención en sucursal", "4.223 (32%)", "8.808 (66%)", "100%", "3.816 (29%)", "No (plantilla)"],
    ["Calidad de servicio", "4.219 (32%)", "8.837 (67%)", "100%", "3.738 (28%)", "No (plantilla)"],
], [3.4, 2.3, 2.3, 2.6, 2.3, 2.4], size=8.5, bold_first=True)
p("Montos reclamados (20.711 con monto, en USD): mediana 14, un cuarto supera 285, máximo 5.000; 4.723 superan 500 USD. Igual en los cinco tipos.")
rich([("Lo que esto significa para el tratamiento: ", "b"), "ninguna queja llega con evidencia utilizable. El sistema tiene que construirla en la conversación y contra las tablas del cliente (sección 3, paso 'verificar')."])

h("2.3 Qué pasa hoy con cada tipo (estado y criterios de urgencia)", 2)
table(["Tipo de queja", "Nunca asignado", "En proceso", "Escalado", "Resuelto o cerrado", "Rechazado", "Fuera de SLA", "Vía regulador", "Reincidente (campo)", "Crítico", "> 500 USD"], [
    ["Cargo no reconocido", "4.040", "5.407", "677", "3.331", "125", "2.739", "156", "1.992", "644", "985"],
    ["Cobro indebido", "4.028", "5.468", "700", "3.224", "133", "2.680", "140", "2.064", "686", "980"],
    ["Problema con app", "3.997", "5.419", "653", "3.198", "140", "2.681", "130", "2.047", "682", "919"],
    ["Atención en sucursal", "4.021", "5.360", "599", "3.226", "155", "2.724", "142", "2.020", "691", "957"],
    ["Calidad de servicio", "4.039", "5.169", "692", "3.142", "152", "2.671", "149", "1.963", "652", "882"],
    ["Total", "20.125", "26.823", "3.321", "16.121", "705", "13.495", "717", "10.086", "3.355", "4.723"],
], [2.6, 1.4, 1.3, 1.3, 1.5, 1.3, 1.3, 1.3, 1.5, 1.1, 1.2], size=7.5, bold_first=True, bold_last=True)
p("Todo se reparte igual entre los cinco tipos, y la prioridad no cambia nada: un caso crítico tarda lo mismo (15-16 días), incumple el plazo igual (19-21%) y sigue abierto igual (75%) que uno de prioridad baja. El banco clasifica pero no actúa distinto. Compensaciones: 4.641 casos (6,9%), 1.174.810 USD, mediana 253 USD.")
pb()

h("2.4 Lo que el dataset no permite saber (y cómo lo resuelve el sistema)", 2)
table(["Lo que no se puede distinguir", "Por qué", "Cómo lo cubre el sistema"], [
    ["El motivo de cada contacto del momento 1", "contact_reason es idéntico a la categoría ('Queja'); los transcripts (25%) son plantillas de consulta de saldo; los productos mencionados no existen o son ajenos", "El clasificador lo registra desde el texto del cliente; se usa la mezcla de los casos formales como estimación"],
    ["Dentro de 'Cobro indebido': duplicado, comisión no informada o monto distinto", "La descripción es la plantilla 'Queja relacionada con fees'", "Preguntas de completitud en la conversación + comparación con tarifa"],
    ["Dentro de 'Cargo no reconocido': fraude real, compra olvidada, comercio con otro nombre", "No hay enlace caso-transacción; el producto es ajeno; fraude y quejas no se conectan (0,21%)", "Búsqueda del cargo en las transacciones del cliente + regla del score de fraude"],
    ["Dentro de 'Problema con app': pantalla y error", "Los eventos digitales no se conectan en el tiempo con las quejas", "Se pide pantalla y fecha; el error se muestra con datos preparados (fixture)"],
    ["Si el caso se resolvió bien", "La satisfacción con la resolución es uniforme de 1 a 5", "'Segunda opinión' del cliente al cerrar"],
    ["Si el cliente es reincidente", "is_repeat_complainer (10.086) no coincide con el historial real (11.179 clientes con 2+)", "Se usa el historial real del cliente"],
], [5.0, 6.0, 5.5], size=8.5)
pb()

# ---------------- 5. FLUJO ----------------
h("3. Cómo se trata cada tipo de queja")
h("3.1 El flujo general (seis pasos)", 2)
num([("Identificar. ", "b"), "Sesión de prueba autenticada (documento + código de app). Sin sesión válida no se muestra ningún dato."])
num([("Entender. ", "b"), "El clasificador local asigna subcategoría e intención (solicitud, reclamo, consulta de estado) con una confianza. ≥ 0,85 se acepta; entre 0,60 y 0,85 el modelo hace una pregunta con las dos opciones más probables; < 0,60 dos veces → humano."])
num([("Verificar. ", "b"), "Se piden solo los datos obligatorios de la subcategoría y se contrastan con las tablas del cliente (cargo existe y es suyo; tarjeta existe; sucursal existe). Esto es lo que hoy nunca ocurre (sección 2.2)."])
num([("Decidir. ", "b"), "Reglas en código eligen la ruta: A (resolver ahora), B (caso con promesa) o C (humano). El modelo nunca decide."])
num([("Actuar. ", "b"), "Respuesta con datos exactos, apertura del caso con número y fecha, o paquete de derivación con cola y prioridad. Toda acción se verifica en el core simulado antes de contarla al cliente."])
num([("Seguir. ", "b"), "Reloj de promesas: 24 h sin asignar → alerta; 80% del SLA → aviso al cliente; vencido → escalamiento. Al cerrar, 'segunda opinión' del cliente; si no está conforme, reabre con prioridad."])

h("3.2 Ruta por tipo de queja y por lo que pide el cliente", 2)
table(["Subcategoría", "Datos obligatorios que se piden", "Verificación contra datos", "Ruta A (se resuelve ahora) si…", "Ruta B (caso con promesa) si…", "Ruta C (humano) si…"], [
    ["Cargo no reconocido\n13.580 · 20%", "Fecha aproximada, monto o comercio; tarjeta (últimos 4)", "Cargo encontrado en transactions del cliente; estado, código, riesgo de fraude",
     "El cliente reconoce el cargo al ver comercio, fecha y monto; o el cargo ya fue revertido", "Cargo verificado, riesgo bajo, cliente no lo reconoce → caso 'Cargo no reconocido' con evidencia",
     "Score de fraude > 30, tarjeta perdida/robada, monto > 500 USD, reincidente → bloqueo con confirmación + cola de Fraudes (2 h)"],
    ["Cobro indebido\n13.553 · 20%", "Cargo + motivo (duplicado, comisión, monto distinto)", "Cargo encontrado; comparación con tarifa publicada (sintética); búsqueda de duplicado",
     "El cobro coincide con la tarifa publicada y el cliente acepta la explicación; o el duplicado ya se revirtió", "Cobro no coincide con tarifa o duplicado sin revertir → caso con evidencia",
     "Monto > 500 USD, reincidente, regulador, pide compensación"],
    ["Problema con app\n13.407 · 20%", "Pantalla, fecha, plataforma", "Evento de error del cliente si existe; versión de app",
     "Hay guía para esa pantalla y el cliente confirma que se resolvió", "Guía no resuelve o error con dinero involucrado → caso a Soporte Técnico",
     "Error repetido tras la guía y dinero descontado, o reincidente"],
    ["Atención en sucursal\n13.361 · 20%", "Sucursal, fecha, qué pasó", "Sucursal existe y estaba abierta ese día",
     "(No aplica: siempre requiere gestión)", "Caso al supervisor de la sucursal con fecha y hecho registrado",
     "Queja sobre una persona identificable, regulador, reincidente"],
    ["Calidad de servicio\n13.194 · 20%", "Canal, fecha, qué pasó", "Contacto previo del cliente ese día si existe",
     "(No aplica)", "Caso a Quejas y Reclamos con el contacto previo adjunto",
     "Regulador, reincidente, disputa de una resolución anterior"],
    ["Solicitud (todas)\n6.761 · 10%", "Qué solicita", "Según lo solicitado (estado de caso, copia, información)",
     "Consulta de estado o información disponible en datos", "Solicitud que requiere trámite → caso simple, sin investigación", "(Rara vez)"],
    ["Sugerencia (todas)\n3.284 · 5%", "Ninguno", "Ninguna", "Se agradece y registra; se cierra en la conversación", "(No aplica)", "(No aplica)"],
], [2.5, 2.7, 2.7, 3.0, 3.0, 2.6], size=7.5, bold_first=True)

h("3.3 Volúmenes por ruta", 2)
table(["Ruta", "Criterio", "Reclamos en 3 años", "Por año", "Por día hábil"], [
    ["C · Humano ahora", "Regulador (717) o reincidente (10.086) o prioridad crítica (3.355) o monto > 500 USD (4.723) o fraude con score > 30", "17.253 (26%)", "5.750", "≈ 16"],
    ["A · Se resuelve ahora", "Meta: sugerencias (3.284) + consultas de estado + cargos y cobros explicados con datos", "≈ 17.000-20.000 (25-30%)", "≈ 6.000", "≈ 17"],
    ["B · Caso con promesa", "El resto", "≈ 30.000-33.000 (45-50%)", "≈ 10.500", "≈ 29"],
], [3.2, 7.0, 2.6, 1.7, 2.0], size=8.5, bold_first=True)
note("La ruta C se calcula con la data (26%). Las rutas A y B son metas: la proporción real de quejas que se resuelven con datos se mide en la evaluación con el conjunto de prueba, porque el dataset no dice cuántos cargos 'no reconocidos' eran en realidad compras olvidadas.")

h("3.4 Vía rápida de fraude (dentro de la ruta C)", 2)
table(["Concepto", "Número exacto"], [
    ["Fraudes reales en 4.425.008 transacciones", "4.316 (0,098%): 1.439 por año, 3,9 por día"],
    ["Aprobados por el banco / rechazados / pendientes o revertidos", "3.986 (92,4%) / 215 / 115"],
    ["Clientes afectados", "4.233"],
    ["Monto aprobado en fraude (3 años)", "6.258.630 USD"],
    ["Transacciones con score > 30", "2.373, y las 2.373 son fraude (precisión 100%)"],
    ["Fraudes que la regla detecta / no detecta", "2.373 (55%) / 1.943 (45%, sin ninguna otra señal)"],
    ["Fraude por tipo de producto", "0,10% de las transacciones en todos: ahorro 1.257, tarjeta de crédito 1.111, cuenta corriente 1.065, débito 437, préstamo personal 230, hipotecario 133, inversión 62, seguro 21"],
    ["Reclamos 'Cargo no reconocido' con fraude real previo (90 días)", "0,21%, igual que los reclamos de sucursal: no hay conexión"],
], [6.0, 10.5], size=9)
p("Flujo: el cliente dice \u201cme robaron la tarjeta\u201d / \u201cno hice esta compra\u201d, o el cargo identificado tiene score > 30 → se listan los cargos recientes con su riesgo → se ofrece bloquear la tarjeta y se ejecuta solo con confirmación explícita, verificando el resultado en el core → se abre el caso 'Cargo no reconocido' con la evidencia → cola de Fraudes (96 agentes activos), prioridad alta, SLA interno 2 h. El chat nunca desbloquea, nunca promete reembolso.")
p("Extensión opcional (si sobra tiempo): aviso por push o correo de cada consumo, como exige la SBS en Perú y hacen Yape, Plin y BCP, con un botón \u201cNo reconozco este consumo\u201d que abre el chat autenticado con el cargo precargado. Los cargos con score > 30 llevan un aviso más fuerte. Volumen en este banco: 4.000 avisos al día; 2 al día con riesgo alto.")

pb()
h("4. Contactos que no son quejas: qué hace el sistema con ellos")
p("Las quejas son el 17% de los contactos. El otro 83% también va a llegar al chat, y el sistema debe saber qué hacer con cada uno sin salirse del alcance (un flujo profundo, no seis a medias).")
table(["Motivo del contacto", "Contactos (3 años)", "%", "Se resuelve hoy", "Qué hace Expediente Vivo"], [
    ["Transaccional (movimientos, pagos, saldos)", "240.056", "35%", "91,5%", "Lo atiende en modo consulta con las mismas herramientas (cargos, tarjetas, saldo): es la ruta A sin abrir caso. Si el cliente descubre un cargo que no reconoce, entra al flujo de queja"],
    ["Producto (cuentas, tarjetas, condiciones)", "150.863", "22%", "89,6%", "Responde lo que está en datos (estado de tarjeta, vencimiento, productos del cliente); lo demás lo deriva al menú de autoservicio o a un humano"],
    ["Queja", "117.021", "17%", "43,6%", "El flujo completo de este documento"],
    ["Técnico (app, web)", "102.899", "15%", "69,9%", "Solo si es una queja de 'problema con app'; el soporte técnico puro se deriva a Soporte Técnico (89 agentes)"],
    ["Comercial (ventas, ofertas)", "54.879", "8%", "65,2%", "Fuera de alcance: mensaje claro y derivación a Ventas (74 agentes). Nunca vende ni promete condiciones"],
    ["Retención (cliente que quiere irse)", "20.578", "3%", "60,2%", "Fuera de alcance: se detecta la intención y se deriva de inmediato a Retención (85 agentes), con lo que el cliente dijo"],
], [4.2, 2.2, 1.0, 1.8, 7.3], size=8.5, bold_first=True)
rich([("Por qué así: ", "b"), "el brief pide un flujo coherente y profundo, y el caso 'ambiguo o no soportado' es obligatorio. Que el sistema reconozca lo que no atiende y lo derive bien (con contexto, a la cola correcta) cuenta como comportamiento correcto, no como falla. "
      "Además, Transaccional es el motivo que hoy mejor se resuelve (91,5%): las consultas de saldo y movimientos salen 'gratis' con las herramientas que ya existen para las quejas, así que el chat sirve para el 52% de los contactos (Transaccional + Queja) desde el primer día."])

doc.save(OUT); print("OK", OUT)
