from sqlalchemy.orm import joinedload
from app.models.request_model import Request
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.user_model import User
from app.models.status_model import Status
from app.models.training_model import Training
from sqlalchemy import func, case, or_
from datetime import datetime, timezone, timedelta
from app.models.institution_model import Institution
from app.models.parish_model import Parish
from app.models.municipality_model import Municipality

# ---------------------------------------------------------------------------
# Bloque Solicitante
# ---------------------------------------------------------------------------

def get_applicant_active_requests(user_id):
    """
    Obtiene las solicitudes activas de la institución a la que pertenece el usuario solicitante.
    Aplica carga ansiosa (joinedload) para evitar consultas N+1 al renderizar.
    """
    user = User.query.get(user_id)
    
    # Validamos que el usuario tenga asociación con el personal institucional
    if not user or not user.person or not user.person.institutional_staff:
        return []
        
    institution_id = user.person.institutional_staff[0].institution_id
    
    # Códigos de estados considerados de cierre
    closed_status = ['STAT-007', 'STAT-008', 'STAT-009']

    # Consulta optimizada con SQLAlchemy
    requests = Request.query.join(InstitutionalStaff).join(
        Status, Request.status_id == Status.id
    ).filter(
        InstitutionalStaff.institution_id == institution_id,
        Request.historical == False,
        Status.status_code.notin_(closed_status)
    ).options(
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.status),
        joinedload(Request.plannings)
    ).order_by(Request.updated_at.desc()).all()
    
    return requests


def check_request_duplicity(institution_id: int, training_id: int) -> dict:
    """
    Verifica de forma cruzada si una Institución Educativa ya posee una solicitud activa
    sobre un tema formativo específico (Validación Institucional, no personal).
    """
    closed_status = ['STAT-007', 'STAT-008', 'STAT-009']
    
    existing = Request.query.join(InstitutionalStaff).join(
        Status, Request.status_id == Status.id
    ).filter(
        InstitutionalStaff.institution_id == institution_id,
        Request.training_id == training_id,
        Request.historical == False,
        Status.status_code.notin_(closed_status)
    ).first()
    
    if existing:
        return {
            "is_duplicate": True,
            "code": existing.request_code,
            "status": existing.status.status_name
        }
    return {"is_duplicate": False}

def _generate_request_code() -> str:
    """Genera un código correlativo único (REQ-YYYY-XXXXX) para la solicitud."""
    from datetime import datetime
    year = datetime.now().year
    prefix = f"REQ-{year}-"
    
    last_req = Request.query.filter(Request.request_code.like(f"{prefix}%")).order_by(Request.id.desc()).first()
    if last_req and last_req.request_code.startswith(prefix):
        # Extraemos el correlativo final
        last_num = int(last_req.request_code.replace(prefix, ""))
        new_num = last_num + 1
    else:
        new_num = 1
        
    return f"{prefix}{new_num:05d}"


def create_training_request(user_id: int, training_id: int, description: str) -> tuple[bool, str, int]:
    """
    Registra una nueva solicitud (Wizard US-34) de forma transaccional.
    Valida la existencia del usuario, asociación institucional y duplicidad.
    Tras guardar, compila el Ticket PDF y dispara el correo asíncrono.
    """
    from app.extensions import db
    user = User.query.get(user_id)
    
    if not user or not user.person or not user.person.institutional_staff:
        return False, "Usuario no autorizado o sin afiliación institucional.", 0
        
    institutional_staff_id = user.person.institutional_staff[0].id
    institution_id = user.person.institutional_staff[0].institution_id
    
    # 1. Validación anti-duplicidad (Institucional)
    duplicity_check = check_request_duplicity(institution_id, training_id)
    
    if duplicity_check.get("is_duplicate"):
        return False, f"Su institución educativa ya posee una solicitud activa para este mismo tema formativo (Trámite: {duplicity_check.get('code')}). Por favor, elija un tema distinto.", 0
        
    # 2. Buscar Estatus inicial 'Nuevo' (STAT-003)
    status_new = Status.query.filter_by(status_code='STAT-003').first()
    if not status_new:
        return False, "Error interno de sistema: Código de estado inicial no encontrado.", 0
        
    # 3. Transacción atómica
    try:
        new_request = Request(
            request_code=_generate_request_code(),
            institutional_staff_id=institutional_staff_id,
            training_id=training_id,
            description=description.strip(),
            status_id=status_new.id,
            historical=False
        )
        db.session.add(new_request)
        db.session.commit()
        
        # 4. Compilación de PDF y Despacho Asíncrono de Correo
        try:
            from app.utils.pdf_generator import generate_receipt_ticket_pdf
            from app.utils.email_utils import send_request_receipt_email
            
            pdf_buffer, _ = generate_receipt_ticket_pdf(new_request)
            pdf_bytes = pdf_buffer.read()
            
            full_name = f"{user.person.first_name} {user.person.last_name}"
            institution_name = user.person.institutional_staff[0].institution.institution_name
            
            send_request_receipt_email(
                to_email=user.person.email,
                full_name=full_name,
                institution_name=institution_name,
                request_code=new_request.request_code,
                pdf_bytes=pdf_bytes
            )
        except Exception as e:
            # Tolerancia a fallos: Si el correo falla, la solicitud sigue siendo válida en la base de datos
            import logging
            logging.getLogger(__name__).error(f"Fallo al emitir comprobante para {new_request.request_code}: {e}")
            
        return True, "Solicitud radicada de forma exitosa.", new_request.id
    except Exception as e:
        db.session.rollback()
        return False, "Ocurrió un error en la base de datos al registrar la solicitud.", 0

# ---------------------------------------------------------------------------
# Bloque Administrador Estadal
# ---------------------------------------------------------------------------

def get_admin_state_id(user: User) -> int | None:
    """
    Extrae de forma segura el state_id al que pertenece el administrador.
    Retorna None si la cadena de relaciones está incompleta, previniendo Error 500.
    """
    try:
        # Safe traversal a través de relaciones
        return user.person.company_staff[0].place.parish.municipality.state_id
    except (AttributeError, IndexError):
        return None


def get_state_dashboard_metrics(state_id: int) -> dict:
    """
    Calcula los 4 KPIs del Dashboard Estadal en un solo viaje a la Base de Datos
    utilizando agregación condicional (case) para máximo rendimiento.
    """
    from app.extensions import db
    query = db.session.query(
        func.count(Request.id).label('total_activas'),
        func.count(case((Status.status_code == 'STAT-006', 1))).label('en_proceso'),
        func.count(case((Status.status_code == 'STAT-007', 1))).label('completadas'),
        func.count(case((Status.status_code.in_(['STAT-003', 'STAT-004', 'STAT-005']), 1))).label('pendientes')
    ).join(InstitutionalStaff, Request.institutional_staff_id == InstitutionalStaff.id) \
     .join(Institution, InstitutionalStaff.institution_id == Institution.id) \
     .join(Parish, Institution.parish_id == Parish.id) \
     .join(Municipality, Parish.municipality_id == Municipality.id) \
     .join(Status, Request.status_id == Status.id) \
     .filter(
         Municipality.state_id == state_id,
         Request.historical == False
     )
    
    result = query.first()
    return {
        'total_activas': result.total_activas or 0,
        'en_proceso': result.en_proceso or 0,
        'completadas': result.completadas or 0,
        'pendientes': result.pendientes or 0
    }


def get_state_requests_paginated(state_id: int, page: int = 1, per_page: int = 10, search_query: str = None, status_id: int = None, municipality_id: int = None):
    """
    Obtiene las solicitudes del estado con carga ansiosa (joinedload) y aplica filtros.
    Calcula dinámicamente el semáforo (Traffic Light) en base al tiempo transcurrido.
    """
    # 1. Join estructural para filtrado (Obligatorio para state_id)
    query = Request.query.join(InstitutionalStaff).join(Institution).join(Parish).join(Municipality).join(
        Status, Request.status_id == Status.id
    ).filter(
        Municipality.state_id == state_id,
        Request.historical == False
    )

    # 2. Eager Loading para evitar queries N+1 durante el renderizado
    query = query.options(
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality),
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.status),
        joinedload(Request.attended_by)
    )

    # Filtros Dinámicos Expresos
    if status_id:
        query = query.filter(Request.status_id == status_id)
    if municipality_id:
        query = query.filter(Municipality.id == municipality_id)

    # 3. Filtro reactivo por término de búsqueda (Universal Search)
    if search_query:
        search_term = f"%{search_query.strip()}%"
        query = query.filter(
            or_(
                Institution.institution_name.ilike(search_term),
                Request.request_code.ilike(search_term),
                Request.training.has(Training.name.ilike(search_term)),
                Municipality.name.ilike(search_term),
                Parish.name.ilike(search_term)
            )
        )

    # 4. Ordenamiento por Semáforo de Prioridad Estricto (Business Logic Sorting)
    priority_case = case(
        (Status.status_code == 'STAT-003', 1), # Prioridad 1: Rojo (Nuevo)
        (Status.status_code.in_(['STAT-004', 'STAT-005', 'STAT-006']), 2), # Prioridad 2: Amarillo (Pendiente/Planificada/En Proceso)
        (Status.status_code.in_(['STAT-007', 'STAT-008', 'STAT-009']), 3), # Prioridad 3: Verde (Completado/Rechazado/Cancelado)
        else_=4
    )
    
    # Ordenamos primero por la Prioridad calculada, y luego cronológicamente (las más antiguas primero)
    query = query.order_by(priority_case.asc(), Request.created_at.asc())
    
    # 5. Paginación segura (error_out=False evita Crash por página fuera de rango)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 6. Cálculo del Semáforo de Tiempos y Alertas Visuales
    vzla_tz = timezone(timedelta(hours=-4))
    now_local = datetime.now(vzla_tz)

    for req in pagination.items:
        status_code = req.status.status_code
        base_text = req.status.status_name
        
        # Tiempo desde la radicación (Para solicitudes Nuevas)
        if req.created_at:
            created_local = req.created_at.astimezone(vzla_tz)
            hours_diff_created = (now_local - created_local).total_seconds() / 3600
        else:
            hours_diff_created = 0
            
        # Tiempo desde la última actualización (Aceptación/Planificación)
        if req.updated_at:
            updated_local = req.updated_at.astimezone(vzla_tz)
            hours_diff_updated = (now_local - updated_local).total_seconds() / 3600
        else:
            hours_diff_updated = 0
            
        # Asignación Dinámica
        if status_code in ['STAT-007', 'STAT-008', 'STAT-009']:
            req.traffic_light_color = 'green'
            req.traffic_light_text = base_text
            
        elif status_code == 'STAT-003':
            req.traffic_light_color = 'red'
            # Límite 3 días para atender una solicitud nueva
            if hours_diff_created > 72:
                req.traffic_light_text = f'{base_text} (Límite Excedido)'
            elif hours_diff_created > 48:
                req.traffic_light_text = f'{base_text} (+2 días sin atender)'
            else:
                req.traffic_light_text = base_text
                
        elif status_code in ['STAT-004', 'STAT-005', 'STAT-006']:
            req.traffic_light_color = 'yellow'
            # Límite 10 días para ejecutarla (desde que cambió de estatus)
            days_elapsed = int(hours_diff_updated / 24)
            days_remaining = 10 - days_elapsed
            
            if days_remaining < 0:
                req.traffic_light_text = f'{base_text} (Límite Excedido)'
            elif days_remaining <= 3:
                # Mostrar cuenta regresiva de alerta (-3, -2, -1)
                req.traffic_light_text = f'{base_text} (Quedan {days_remaining} días)'
            else:
                req.traffic_light_text = base_text
        else:
            # Fallback
            req.traffic_light_color = 'yellow'
            req.traffic_light_text = base_text

    return pagination

def get_request_full_detail(request_id: int):
    """
    Obtiene la radiografía completa de una solicitud (Ficha Técnica).
    Calcula dinámicamente si la solicitud está en demora por ANS.
    """
    req = Request.query.options(
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.person),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality),
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.status),
        joinedload(Request.attended_by),
        joinedload(Request.plannings),
        joinedload(Request.justifications)
    ).get_or_404(request_id)

    # Evaluación de bloqueo ANS
    vzla_tz = timezone(timedelta(hours=-4))
    now_local = datetime.now(vzla_tz)
    has_delay_block = False

    status_code = req.status.status_code

    if status_code == 'STAT-003':
        if req.created_at:
            hours_diff = (now_local - req.created_at.astimezone(vzla_tz)).total_seconds() / 3600
            if hours_diff > 72:
                has_delay_block = True
    elif status_code in ['STAT-004', 'STAT-005', 'STAT-006']:
        if req.updated_at:
            hours_diff = (now_local - req.updated_at.astimezone(vzla_tz)).total_seconds() / 3600
            if hours_diff > 240:
                has_delay_block = True

    # Si posee justificaciones previas registradas para este retraso, se levanta el bloqueo visual temporal
    if has_delay_block and req.justifications:
        for just in req.justifications:
            if just.justification_type in ['RETRASO', 'REPROGRAMACION']:
                has_delay_block = False
                break
                
    req.has_delay_block = has_delay_block
    # ---------------------------------------------------------
    # Semáforo de Tiempos y Alertas Visuales 
    # ---------------------------------------------------------
    base_text = req.status.status_name
    if status_code in ['STAT-007', 'STAT-008', 'STAT-009']:
        req.traffic_light_color = 'green'
        req.traffic_light_text = base_text
    elif status_code == 'STAT-003':
        req.traffic_light_color = 'red'
        if req.created_at:
            if hours_diff > 72:
                req.traffic_light_text = f'{base_text} (Límite Excedido)'
            elif hours_diff > 48:
                req.traffic_light_text = f'{base_text} (+2 días sin atender)'
            elif hours_diff > 24:
                req.traffic_light_text = f'{base_text} (+1 día sin atender)'
            else:
                req.traffic_light_text = base_text
        else:
            req.traffic_light_text = base_text
    elif status_code in ['STAT-004', 'STAT-005', 'STAT-006']:
        req.traffic_light_color = 'yellow'
        if req.updated_at:
            days_elapsed = int(hours_diff / 24)
            days_remaining = 10 - days_elapsed
            
            if days_remaining < 0:
                req.traffic_light_text = f'{base_text} (Límite Excedido)'
            elif days_remaining <= 3:
                req.traffic_light_text = f'{base_text} (Quedan {days_remaining} días)'
            else:
                req.traffic_light_text = base_text
        else:
            req.traffic_light_text = base_text
    else:
        req.traffic_light_color = 'yellow'
        req.traffic_light_text = base_text

    return req
