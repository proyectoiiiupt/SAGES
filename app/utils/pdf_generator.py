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
    dea_code = institution.plantel_code if hasattr(institution, 'plantel_code') else "N/A"
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
        [Paragraph("<b>Código DEA:</b>", normal_style), Paragraph(dea_code, normal_style)],
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
        [Paragraph("<b>Código de Trámite:</b>", normal_style), Paragraph(f"<b>{request_obj.request_code}</b>", normal_style)],
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
