import os
import io
from datetime import timezone, datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.utils.qr_generator import create_receipt_qr

def get_spanish_month(month_num):
    months = ["enero", "febrero", "marzo", "abril", "mayo", "junio", 
              "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return months[month_num - 1]

def generate_receipt_ticket_pdf(request_obj) -> tuple[io.BytesIO, str]:
    """
    Maqueta y compila un documento PDF vectorial oficial en memoria.
    Retorna el flujo de bytes (buffer) del PDF y el token de seguridad.
    """
    buffer = io.BytesIO()
    
    # Configuramos el lienzo del PDF (Ajustamos topMargin para dejar espacio al cintillo más grueso)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, 
        leftMargin=40,
        topMargin=95,  # Aumentado a 95 para compensar el nuevo grosor del cintillo
        bottomMargin=20
    )
    
    # 1. Extracción de Modelos (ORM)
    staff = request_obj.institutional_staff
    institution = staff.institution
    training = request_obj.training
    module = training.training_module
    
    # 2. Hojas de Estilo
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading2'],
        alignment=1, # Centro
        fontSize=13, # Ligeramente más pequeño
        spaceAfter=5,
        textColor=colors.HexColor("#1c3d73")
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 9 # Reducimos 1pt para ahorrar espacio
    bold_style = ParagraphStyle('BoldStyle', parent=normal_style, fontName='Helvetica-Bold', fontSize=9)
    
    date_style = ParagraphStyle(
        'DateStyle',
        parent=normal_style,
        fontName='Helvetica-Bold',
        alignment=2, # Derecha
        spaceAfter=10
    )
    
    elements = []
    
    # 3. Rutas de Imágenes
    base_dir = os.path.dirname(os.path.dirname(__file__))
    cintillo_path = os.path.join(base_dir, 'static', 'img', 'mppee-cintillo.jpg')
    logo_path = os.path.join(base_dir, 'static', 'img', 'logo_corpoelec.png')
    
    # Función Callback para dibujar el cintillo absoluto (Borde a borde)
    def draw_full_bleed_header(canvas, document):
        if os.path.exists(cintillo_path):
            page_width, page_height = letter
            # Incrementamos la altura del cintillo de 50 a 75 para que deje de verse estirado/delgado
            cintillo_height = 75
            # Dibujamos directamente sobre el lienzo (canvas) en la coordenada absoluta (X=0, Y=tope)
            canvas.drawImage(cintillo_path, 0, page_height - cintillo_height, width=page_width, height=cintillo_height, preserveAspectRatio=False)

    # 4. Encabezado Institucional (Solo el Logo, el cintillo va por Canvas)
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=140, height=55, kind='proportional')
        elements.append(logo)
        elements.append(Spacer(1, 10))
        
    # 5. Fecha Actual de Emisión Formateada (Zona Horaria Venezuela UTC-4)
    from datetime import timedelta
    vzla_tz = timezone(timedelta(hours=-4))
    now = datetime.now(vzla_tz)
    date_formatted = f"{now.day} de {get_spanish_month(now.month)} del {now.year}"
    elements.append(Paragraph(date_formatted, date_style))
    
    # 6. Título Central
    elements.append(Paragraph("<b>COMPROBANTE DE RECEPCIÓN DE SOLICITUD</b>", title_style))
    elements.append(Spacer(1, 5))
    
    # 7. Saludo y Mensaje Formal de Trámite
    greeting_text = (
        "Reciba un cordial y respetuoso saludo.<br/><br/>"
        "A través del presente documento, el Ministerio del Poder Popular para la Energía Eléctrica y "
        "la Corporación Eléctrica Nacional (CORPOELEC) certifican la recepción exitosa de su solicitud de formación "
        "en materia de Uso Racional y Eficiente de la Energía (UREE).<br/><br/>"
        "Su requerimiento ha sido registrado formalmente en nuestro sistema y será derivado al equipo pedagógico "
        "correspondiente para su evaluación técnica. En los próximos días hábiles, un analista de la Coordinación "
        "se pondrá en contacto con su institución para coordinar los detalles operativos de la actividad."
    )
    elements.append(Paragraph(greeting_text, ParagraphStyle('Greeting', parent=normal_style, alignment=4, leading=12)))
    elements.append(Spacer(1, 10))
    
    # 8. Datos de la Institución Educativa (Sección 1)
    inst_type_str = institution.institution_type.name if (institution and hasattr(institution, 'institution_type') and institution.institution_type) else "Educativa"
    try:
        parish_name = institution.parish.name
        municipality_name = institution.parish.municipality.name
        state_name = institution.parish.municipality.state.name
        location_str = f"{state_name} / {municipality_name} / {parish_name}"
    except AttributeError:
        location_str = "Información de ubicación no disponible"
    
    inst_data = [
        [Paragraph("<b>DATOS DE LA INSTITUCIÓN EDUCATIVA</b>", bold_style), ""],
        [Paragraph("<b>Nombre:</b>", normal_style), Paragraph(institution.institution_name, normal_style)],
        [Paragraph("<b>Tipo de Institución:</b>", normal_style), Paragraph(inst_type_str, normal_style)],
        [Paragraph("<b>Ubicación:</b>", normal_style), Paragraph(location_str, normal_style)],
    ]
    inst_table = Table(inst_data, colWidths=[150, 350])
    inst_table.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('BACKGROUND', (0,0), (1,0), colors.HexColor("#019577")),
        ('TEXTCOLOR', (0,0), (1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    elements.append(inst_table)
    elements.append(Spacer(1, 10))
    
    # 9. Datos de Solicitud (Sección 2)
    if request_obj.created_at:
        local_date = request_obj.created_at.astimezone(vzla_tz)
        date_str = local_date.strftime("%d/%m/%Y %I:%M %p")
    else:
        date_str = "N/A"
        
    requester_person = staff.person
    requester_name = f"{requester_person.first_name} {requester_person.last_name}"
        
    id_data = [
        [Paragraph("<b>DATOS DE SOLICITUD</b>", bold_style), ""],
        [Paragraph("<b>Condición de Trámite:</b>", normal_style), Paragraph("<b>Solicitud Registrada en Plataforma</b>", normal_style)],
        [Paragraph("<b>Solicitante:</b>", normal_style), Paragraph(requester_name, normal_style)],
        [Paragraph("<b>Fecha de Radicación:</b>", normal_style), Paragraph(date_str, normal_style)],
        [Paragraph("<b>Estatus Actual:</b>", normal_style), Paragraph(request_obj.status.status_name, normal_style)]
    ]
    id_table = Table(id_data, colWidths=[150, 350])
    id_table.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('BACKGROUND', (0,0), (1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    elements.append(id_table)
    elements.append(Spacer(1, 10))
    
    # 10. Datos del Requerimiento Pedagógico (Sección 3)
    req_data = [
        [Paragraph("<b>REQUERIMIENTO PEDAGÓGICO</b>", bold_style), ""],
        [Paragraph("<b>Módulo Rector:</b>", normal_style), Paragraph(module.name, normal_style)],
        [Paragraph("<b>Tema Formativo:</b>", normal_style), Paragraph(training.name, normal_style)],
        [Paragraph("<b>Justificación de la Solicitud:</b>", normal_style), Paragraph(request_obj.description, normal_style)],
    ]
    req_table = Table(req_data, colWidths=[150, 350])
    req_table.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('BACKGROUND', (0,0), (1,0), colors.HexColor("#336699")),
        ('TEXTCOLOR', (0,0), (1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP')
    ]))
    elements.append(req_table)
    elements.append(Spacer(1, 15))
    
    # 11. Generar Código QR Criptográfico y Bloque de Autenticación
    token, qr_buffer = create_receipt_qr(request_obj.request_code, request_obj.id)
    qr_img = Image(qr_buffer, width=80, height=80)
    
    short_token = token[:16].upper()
    formatted_token = f"{short_token[:4]}-{short_token[4:8]}-{short_token[8:12]}-{short_token[12:16]}"
    
    legal_text = (
        "<font size=8><b>Sello Digital de Autenticidad SAGES</b></font><br/><br/>"
        "<font size=8>Documento oficial generado automatizadamente por el Sistema SAGES.<br/>"
        "Escanee el código QR adjunto con cualquier dispositivo inteligente para verificar "
        "la legitimidad y conocer el estatus en tiempo real de este trámite en el portal de CORPOELEC.<br/><br/>"
        f"<b>Código de Autenticidad:</b> {formatted_token}</font>"
    )
    
    qr_data = [
        [qr_img, Paragraph(legal_text, normal_style)]
    ]
    qr_table = Table(qr_data, colWidths=[90, 410])
    qr_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,-1), 'CENTER')
    ]))
    
    elements.append(qr_table)
    elements.append(Spacer(1, 10))
    
    # 12. Cierre Formal Despedida
    closing_style = ParagraphStyle('Closing', parent=normal_style, alignment=1, spaceBefore=0) # 1 es Centro
    
    elements.append(Paragraph("Agradeciendo de antemano su invaluable interés en fomentar la cultura del uso eficiente de la energía.", closing_style))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph("<b>Atentamente,</b>", closing_style))
    elements.append(Paragraph("<b>La Corporación Eléctrica Nacional (CORPOELEC)</b>", closing_style))
    
    # 13. Compilación del Documento en RAM (Pasando el Callback del Cintillo)
    doc.build(elements, onFirstPage=draw_full_bleed_header)
    
    # Rebobinar el buffer para que sea leíble por la capa de Correo o Descarga
    buffer.seek(0)
    
    return buffer, token


def generate_completion_report_pdf(request_obj_or_id) -> io.BytesIO:
    """
    Maqueta y compila en memoria RAM el Informe Técnico Final de Cumplimiento (US-50).
    Aplica diseño corporativo oficial con membrete CORPOELEC, resumen pedagógico,
    inventario de evidencias y sello digital QR de validación criptográfica.
    Retorna flujo binario io.BytesIO listo para descarga inmediata.
    """
    from sqlalchemy.orm import joinedload
    from app.models.request_model import Request
    from app.models.training_model import Training
    from app.models.training_module_model import TrainingModule
    from app.models.institutional_staff_model import InstitutionalStaff
    from app.models.institution_model import Institution
    from app.models.parish_model import Parish
    from app.models.municipality_model import Municipality
    from app.models.state_model import State
    from app.models.user_model import User
    from flask import current_app
    from app.utils.qr_generator import generate_verification_token, generate_qr_buffer
    from datetime import timedelta

    # 1. Obtener objeto Request con todas sus relaciones
    if isinstance(request_obj_or_id, (int, str)):
        req = Request.query.options(
            joinedload(Request.status),
            joinedload(Request.training).joinedload(Training.training_module),
            joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.person),
            joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
            joinedload(Request.attended_by).joinedload(User.person),
            joinedload(Request.plannings),
            joinedload(Request.evidences)
        ).get(int(request_obj_or_id))
    else:
        req = request_obj_or_id

    if not req:
        raise ValueError("Expediente de solicitud no encontrado.")

    # Restricción de Negocio Estricta: Solo solicitudes Completadas (STAT-007)
    status_code = req.status.status_code if req.status else ''
    if status_code != 'STAT-007':
        raise ValueError("El informe técnico solo puede generarse para solicitudes concluidas en estado Completado (STAT-007).")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=95,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    normal_style = styles['Normal']
    normal_style.fontSize = 8.5
    normal_style.leading = 11

    title_style = ParagraphStyle(
        'RepTitleStyle',
        parent=styles['Heading2'],
        alignment=1, # Centro
        fontSize=12,
        spaceAfter=4,
        textColor=colors.HexColor("#1c3d73"),
        fontName='Helvetica-Bold'
    )

    subtitle_style = ParagraphStyle(
        'RepSubtitleStyle',
        parent=normal_style,
        alignment=1,
        fontSize=9,
        textColor=colors.HexColor("#4b5563"),
        spaceAfter=8
    )

    bold_style = ParagraphStyle('RepBoldStyle', parent=normal_style, fontName='Helvetica-Bold', fontSize=8.5)
    header_col_style = ParagraphStyle('RepHeaderCol', parent=normal_style, fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.white)

    date_style = ParagraphStyle(
        'RepDateStyle',
        parent=normal_style,
        fontName='Helvetica',
        fontSize=8.5,
        alignment=2, # Derecha
        spaceAfter=8
    )

    elements = []

    # Cintillo y Logo Institucionales
    base_dir = os.path.dirname(os.path.dirname(__file__))
    cintillo_path = os.path.join(base_dir, 'static', 'img', 'mppee-cintillo.jpg')
    logo_path = os.path.join(base_dir, 'static', 'img', 'logo_corpoelec.png')

    def draw_full_bleed_header(canvas, document):
        if os.path.exists(cintillo_path):
            page_width, page_height = letter
            cintillo_height = 75
            canvas.drawImage(cintillo_path, 0, page_height - cintillo_height, width=page_width, height=cintillo_height, preserveAspectRatio=False)

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=130, height=50, kind='proportional')
        elements.append(logo)
        elements.append(Spacer(1, 4))

    # Fecha oficial de emisión (Zona horaria Venezuela UTC-4)
    vzla_tz = timezone(timedelta(hours=-4))
    now = datetime.now(vzla_tz)
    date_formatted = f"Caracas, {now.day} de {get_spanish_month(now.month)} de {now.year}"
    elements.append(Paragraph(date_formatted, date_style))

    # Títulos Centrales
    elements.append(Paragraph("<b>INFORME TÉCNICO DE CUMPLIMIENTO</b>", title_style))
    elements.append(Paragraph("<b>DIVISIÓN DE USO RACIONAL Y EFICIENTE DE LA ENERGÍA (UREE)</b>", subtitle_style))
    elements.append(Spacer(1, 4))

    intro_text = (
        "La Corporación Eléctrica Nacional (CORPOELEC), adscrita al Ministerio del Poder Popular para la Energía "
        "Eléctrica (MPPEE), a través de la Coordinación Estadal de Uso Racional y Eficiente de la Energía (UREE), "
        "certifica mediante el presente documento la ejecución satisfactoria y culminación formal de la jornada formativa "
        "comunitaria impartida a la institución educativa que se detalla a continuación:"
    )
    elements.append(Paragraph(intro_text, ParagraphStyle('Intro', parent=normal_style, alignment=4, leading=12)))
    elements.append(Spacer(1, 8))

    # Bloque I: Identificación Institucional
    staff = req.institutional_staff
    institution = staff.institution if staff else None
    inst_type_str = institution.institution_type.name if (institution and hasattr(institution, 'institution_type') and institution.institution_type) else "Educativa"
    try:
        parish_name = institution.parish.name
        municipality_name = institution.parish.municipality.name
        state_name = institution.parish.municipality.state.name
        location_str = f"{state_name} / {municipality_name} / {parish_name}"
    except AttributeError:
        location_str = "No disponible"

    address_str = institution.address if (institution and institution.address) else "Dirección no registrada"

    inst_data = [
        [Paragraph("<b>I. IDENTIFICACIÓN DE LA INSTITUCIÓN EDUCATIVA</b>", header_col_style), ""],
        [Paragraph("<b>Nombre del Plantel:</b>", bold_style), Paragraph(institution.institution_name if institution else "N/A", normal_style)],
        [Paragraph("<b>Tipo de Institución:</b>", bold_style), Paragraph(inst_type_str, normal_style)],
        [Paragraph("<b>Jurisdicción:</b>", bold_style), Paragraph(location_str, normal_style)],
        [Paragraph("<b>Dirección Sede:</b>", bold_style), Paragraph(address_str, normal_style)],
    ]
    inst_table = Table(inst_data, colWidths=[140, 400])
    inst_table.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('BACKGROUND', (0,0), (1,0), colors.HexColor("#019577")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('PADDING', (0,0), (-1,-1), 3.5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    elements.append(inst_table)
    elements.append(Spacer(1, 8))

    # Bloque II: Memoria Pedagógica y Facilitador
    training = req.training
    module = training.training_module if training else None

    # Fecha de ejecución
    execution_date_str = "Concluida según cronograma"
    if req.finished_at:
        fin_local = req.finished_at.astimezone(vzla_tz)
        execution_date_str = fin_local.strftime("%d/%m/%Y")
    elif req.plannings:
        plans = [p for p in req.plannings if p.planned_for]
        if plans:
            latest_plan = max(plans, key=lambda p: p.planned_for)
            execution_date_str = latest_plan.planned_for.strftime("%d/%m/%Y")

    # Facilitador
    if req.attended_by and req.attended_by.person:
        p_fac = req.attended_by.person
        facilitator_str = f"{p_fac.first_name} {p_fac.last_name} (Funcionario UREE / CORPOELEC)"
    else:
        facilitator_str = "Equipo Técnico de la Coordinación Estadal UREE"

    pedagogical_data = [
        [Paragraph("<b>II. MEMORIA PEDAGÓGICA Y ESTADO INSTITUCIONAL</b>", header_col_style), ""],
        [Paragraph("<b>Condición Operativa:</b>", bold_style), Paragraph("<b>Jornada Ejecutada y Culminada Satisfactoriamente</b>", normal_style)],
        [Paragraph("<b>Módulo Rector:</b>", bold_style), Paragraph(module.name if module else "N/A", normal_style)],
        [Paragraph("<b>Tema Formativo:</b>", bold_style), Paragraph(training.name if training else "N/A", normal_style)],
        [Paragraph("<b>Fecha de Ejecución:</b>", bold_style), Paragraph(execution_date_str, normal_style)],
        [Paragraph("<b>Facilitador Responsable:</b>", bold_style), Paragraph(facilitator_str, normal_style)],
    ]
    ped_table = Table(pedagogical_data, colWidths=[140, 400])
    ped_table.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('BACKGROUND', (0,0), (1,0), colors.HexColor("#1c3d73")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('PADDING', (0,0), (-1,-1), 3.5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    elements.append(ped_table)
    elements.append(Spacer(1, 8))

    # Bloque III: Resumen de Actividad y Evidencias Custodiadas
    ev_count = len(req.evidences) if req.evidences else 0
    activity_summary = (
        f"Se impartió la acción pedagógica comunitaria orientada a la concienciación sobre el uso eficiente de la "
        f"energía eléctrica, orientando a docentes, directivos y estudiantes en hábitos de consumo responsable. "
        f"El expediente cuenta con un total de <b>{ev_count} evidencia(s) documental(es) custodiada(s)</b> en la bóveda digital "
        f"de SAGES, integrando minutas de asistencia, acta de cierre y registros fotográficos de la jornada."
    )

    act_data = [
        [Paragraph("<b>III. SÍNTESIS DE LA ACTIVIDAD FORMATIVA</b>", header_col_style)],
        [Paragraph(activity_summary, ParagraphStyle('ActText', parent=normal_style, alignment=4, leading=12))]
    ]
    act_table = Table(act_data, colWidths=[540])
    act_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), colors.HexColor("#336699")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP')
    ]))
    elements.append(act_table)
    elements.append(Spacer(1, 10))

    # Bloque IV: Certificación y Código QR Criptográfico
    token = generate_verification_token(req.request_code, req.id)
    base_url = current_app.config.get('APP_BASE_URL', 'http://127.0.0.1:5000')
    canonical_url = f"{base_url}/requests/verify/{token}"
    qr_buffer = generate_qr_buffer(canonical_url)
    qr_img = Image(qr_buffer, width=72, height=72)

    short_token = token[:16].upper()
    formatted_token = f"{short_token[:4]}-{short_token[4:8]}-{short_token[8:12]}-{short_token[12:16]}"

    cert_text = (
        "<font size=8.5><b>Sello Digital de Autenticidad y Validación Institucional</b></font><br/>"
        "<font size=7.5 color='#4b5563'>Documento oficial emitido por el Sistema SAGES de CORPOELEC.<br/>"
        "Escanee el código QR adjunto con cualquier dispositivo inteligente para verificar la autenticidad "
        "y validez legal de este informe en el portal público de certificación de CORPOELEC.<br/><br/>"
        f"<b>Código Criptográfico de Verificación:</b> <font color='#1c3d73'><b>{formatted_token}</b></font></font>"
    )

    qr_data = [
        [qr_img, Paragraph(cert_text, normal_style)]
    ]
    qr_table = Table(qr_data, colWidths=[80, 460])
    qr_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#019577")),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('PADDING', (0,0), (-1,-1), 4)
    ]))
    elements.append(qr_table)
    elements.append(Spacer(1, 16))

    # Bloque V: Firmas Institucionales
    sign_data = [
        [
            Paragraph("___________________________________<br/><b>Coordinación Estadal UREE</b><br/>División de Formación Comunitaria", ParagraphStyle('Sign1', parent=normal_style, alignment=1, fontSize=7.5)),
            Paragraph("___________________________________<br/><b>Facilitador Responsable</b><br/>Personal Técnico CORPOELEC", ParagraphStyle('Sign2', parent=normal_style, alignment=1, fontSize=7.5)),
            Paragraph("___________________________________<br/><b>Dirección del Plantel Educativo</b><br/>Sello y Firma de Recepción", ParagraphStyle('Sign3', parent=normal_style, alignment=1, fontSize=7.5))
        ]
    ]
    sign_table = Table(sign_data, colWidths=[180, 180, 180])
    sign_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 2)
    ]))
    elements.append(sign_table)

    # Compilación en RAM
    doc.build(elements, onFirstPage=draw_full_bleed_header)
    buffer.seek(0)
    return buffer

