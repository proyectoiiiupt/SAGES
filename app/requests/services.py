from datetime import datetime, timezone
from sqlalchemy import func, case, or_, and_, text
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models.request_model import Request
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.institution_model import Institution
from app.models.parish_model import Parish
from app.models.municipality_model import Municipality
from app.models.state_model import State
from app.models.user_model import User
from app.models.status_model import Status
from app.models.training_model import Training
from app.models.request_planning_model import RequestPlanning
from app.models.request_justification_model import RequestJustification
from sqlalchemy import func, case, or_
from datetime import datetime, timezone, timedelta

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
            if just.justification_type in ['RETRASO', 'REPROGRAMACION', 'RETRASO_ATENCION', 'RETRASO_EJECUCION']:
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
# ---------------------------------------------------------------------------
# US-38: Monitoreo Nacional con Semáforo y Pre-filtrado
# ---------------------------------------------------------------------------

def _evaluate_traffic_light(req: Request, now_dt: datetime) -> dict:
    """
    Evalúa dinámicamente el semáforo ANS (SLA) Verde / Amarillo / Rojo:

    🟢 Verde  – Dentro del tiempo ANS:
        * STAT-003 / STAT-004 con < 24 h transcurridas.
        * STAT-005 (Planificada) – considerada en norma.
        * STAT-006 (En Proceso) con ≤ 10 días.
        * STAT-007 (Completado) – cerrada en norma.

    🟡 Amarillo – Zona de advertencia:
        * STAT-003 / STAT-004 con entre 24 h y 72 h.

    🔴 Rojo – Crítico / Vencido:
        * STAT-003 / STAT-004 con > 72 h sin atender.
        * STAT-006 (En Proceso) con > 10 días continuos.
    """
    status_code = req.status.status_code if req.status else ''

    # Asegurar fechas con timezone UTC
    created_at = req.created_at
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    elif not created_at:
        created_at = now_dt

    # 1. Completado (STAT-007) → Verde
    if status_code == 'STAT-007':
        finished_at = req.finished_at
        if finished_at and finished_at.tzinfo is None:
            finished_at = finished_at.replace(tzinfo=timezone.utc)

        if finished_at:
            days_to_finish = max(0, (finished_at - created_at).days)
        else:
            days_to_finish = max(0, (now_dt - created_at).days)

        if days_to_finish == 0:
            text = "Cerrada el mismo día"
        elif days_to_finish == 1:
            text = "Cerrada en 1 día"
        else:
            text = f"Cerrada en {days_to_finish} días"

        return {
            "color": "green",
            "badge_class": "badge-ans-green",
            "text": text,
            "risk_level": 3
        }

    # 2. Nuevo (STAT-003) y Pendiente de Revisión (STAT-004)
    if status_code in ('STAT-003', 'STAT-004'):
        delta_seconds = (now_dt - created_at).total_seconds()
        delta_hours = max(0.0, delta_seconds / 3600.0)
        days = int(delta_hours // 24)

        if delta_hours > 72.0:
            # 🔴 Rojo – Límite ANS superado
            text = f"+{days} días sin atender" if days >= 3 else "Límite ANS excedido"
            return {
                "color": "red",
                "badge_class": "badge-ans-red",
                "text": text,
                "risk_level": 1
            }
        elif delta_hours >= 24.0:
            # 🟡 Amarillo – Zona de advertencia (24 h – 72 h)
            day_text = "1 día" if days == 1 else f"{days} días"
            return {
                "color": "yellow",
                "badge_class": "badge-ans-yellow",
                "text": f"{day_text} sin atender",
                "risk_level": 2
            }
        else:
            # 🟢 Verde – Dentro del tiempo ANS (< 24 h)
            return {
                "color": "green",
                "badge_class": "badge-ans-green",
                "text": "En tiempo ANS",
                "risk_level": 3
            }

    # 3. Planificada (STAT-005) → Verde (en norma)
    if status_code == 'STAT-005':
        return {
            "color": "green",
            "badge_class": "badge-ans-green",
            "text": "Planificada",
            "risk_level": 3
        }

    # 4. En Proceso (STAT-006)
    if status_code == 'STAT-006':
        days_in_process = max(0, (now_dt - created_at).days)
        if days_in_process > 10:
            # 🔴 Rojo – Excedió el límite de 10 días en proceso
            return {
                "color": "red",
                "badge_class": "badge-ans-red",
                "text": f"+{days_in_process} días en proceso",
                "risk_level": 1
            }
        else:
            # 🟢 Verde – En proceso dentro del plazo
            days_str = "1 día" if days_in_process == 1 else f"{days_in_process} días"
            return {
                "color": "green",
                "badge_class": "badge-ans-green",
                "text": f"En atención ({days_str})",
                "risk_level": 3
            }

    # Otros estados archivados (STAT-008, STAT-009, etc.) → Gris
    return {
        "color": "gray",
        "badge_class": "badge-ans-gray",
        "text": req.status.status_name if req.status else "Archivada",
        "risk_level": 4
    }




def get_national_monitoring_data(
    state_id: int | None = None,
    search: str | None = None,
    module_id: int | None = None,
    status_id: int | str | None = None,
    page: int = 1,
    per_page: int = 10
) -> dict:
    """
    Obtiene las métricas KPI y el listado paginado de solicitudes para el
    Tablero de Monitoreo Nacional del Super Administrador (US-38).
    Aplica carga ansiosa con joinedload para eliminar el problema N+1.
    """
    now_dt = datetime.now(timezone.utc)

    # ---------------------------------------------------------
    # 1. Agregación de KPIs  (mismos JOINs que la consulta paginada)
    # ---------------------------------------------------------
    kpi_query = db.session.query(
        Status.status_code,
        func.count(Request.id)
    ).select_from(Request).join(
        Status, Request.status_id == Status.id
    ).join(
        InstitutionalStaff, Request.institutional_staff_id == InstitutionalStaff.id
    ).join(
        Institution, InstitutionalStaff.institution_id == Institution.id
    ).join(
        Parish, Institution.parish_id == Parish.id
    ).join(
        Municipality, Parish.municipality_id == Municipality.id
    ).join(
        State, Municipality.state_id == State.id
    ).join(
        Training, Request.training_id == Training.id
    ).filter(
        Request.historical == False
    )

    if state_id:
        kpi_query = kpi_query.filter(Municipality.state_id == state_id)

    if module_id:
        kpi_query = kpi_query.filter(Training.training_module_id == module_id)

    if status_id:
        if isinstance(status_id, int) or (isinstance(status_id, str) and status_id.isdigit()):
            kpi_query = kpi_query.filter(Request.status_id == int(status_id))
        elif isinstance(status_id, str) and status_id.startswith('STAT-'):
            kpi_query = kpi_query.filter(Status.status_code == status_id)

    if search:
        search_clean = search.strip()
        if search_clean:
            search_pattern = f"%{search_clean}%"
            kpi_query = kpi_query.filter(
                or_(
                    Institution.institution_name.ilike(search_pattern),
                    Training.name.ilike(search_pattern)
                )
            )

    status_counts = dict(kpi_query.group_by(Status.status_code).all())

    kpis = {
        "total": sum(status_counts.values()),
        "completed": status_counts.get('STAT-007', 0),
        "in_process": status_counts.get('STAT-006', 0),
        "pending": (
            status_counts.get('STAT-003', 0) +
            status_counts.get('STAT-004', 0) +
            status_counts.get('STAT-005', 0)
        )
    }


    # ---------------------------------------------------------
    # 2. Consulta Paginada de Solicitudes con Carga Ansiosa
    # ---------------------------------------------------------
    query = Request.query.filter(
        Request.historical == False
    ).join(
        Status, Request.status_id == Status.id
    ).join(
        InstitutionalStaff, Request.institutional_staff_id == InstitutionalStaff.id
    ).join(
        Institution, InstitutionalStaff.institution_id == Institution.id
    ).join(
        Parish, Institution.parish_id == Parish.id
    ).join(
        Municipality, Parish.municipality_id == Municipality.id
    ).join(
        State, Municipality.state_id == State.id
    ).join(
        Training, Request.training_id == Training.id
    ).options(
        joinedload(Request.status),
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution)
            .joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.person),
        joinedload(Request.attended_by).joinedload(User.person),
        joinedload(Request.plannings)
    )

    # Filtro Territorial
    if state_id:
        query = query.filter(Municipality.state_id == state_id)

    # Filtro de Búsqueda Textual (Plantel o Tema Formativo)
    if search:
        search_clean = search.strip()
        if search_clean:
            search_pattern = f"%{search_clean}%"
            query = query.filter(
                or_(
                    Institution.institution_name.ilike(search_pattern),
                    Training.name.ilike(search_pattern)
                )
            )

    # Filtro por Módulo
    if module_id:
        query = query.filter(Training.training_module_id == module_id)

    # Filtro por Estatus
    if status_id:
        if isinstance(status_id, int) or (isinstance(status_id, str) and status_id.isdigit()):
            query = query.filter(Request.status_id == int(status_id))
        elif isinstance(status_id, str) and status_id.startswith('STAT-'):
            query = query.filter(Status.status_code == status_id)

    # Ordenamiento: Solicitudes en riesgo primero, luego por created_at DESC
    risk_order = case(
        (Status.status_code.in_(['STAT-003', 'STAT-004']), 1),
        (Status.status_code == 'STAT-006', 2),
        (Status.status_code == 'STAT-005', 3),
        (Status.status_code == 'STAT-007', 4),
        else_=5
    )
    query = query.order_by(risk_order.asc(), Request.created_at.desc())

    # Cota de Paginación Defensiva
    safe_page = max(1, page) if isinstance(page, int) else 1
    safe_per_page = min(max(1, per_page), 50) if isinstance(per_page, int) else 10

    pagination = query.paginate(page=safe_page, per_page=safe_per_page, error_out=False)

    # Evaluación dinámica del semáforo para cada elemento retornado
    for req in pagination.items:
        req.traffic_light = _evaluate_traffic_light(req, now_dt)

    return {
        "kpis": kpis,
        "pagination": pagination,
        "requests": pagination.items
    }


# ---------------------------------------------------------------------------
# US-38-actividad2: Auditoría de Retrasos SLA y Exigencia Coercitiva
# ---------------------------------------------------------------------------

def get_delays_audit_data(
    user,
    state_id: int | None = None,
    justification_status: str = 'all',
    search: str | None = None,
    page: int = 1,
    per_page: int = 10
) -> dict:
    """
    Obtiene los expedientes que han vulnerado los tiempos normativos ANS (SLA)
    para el panel de fiscalización del Super Administrador (Vista A.2).
    
    Criterios de Mora Obligatorios:
      1. Atención Inicial (> 72 horas continuas):
         Status in ('STAT-003', 'STAT-004') and (NOW() - created_at > 72 hours)
      2. Ejecución Presencial (> 10 días continuos):
         Status == 'STAT-006' and (NOW() - accepted_at > 10 days o NOW() - created_at > 10 days)
    """
    now_dt = datetime.now(timezone.utc)

    # Subconsulta para planificaciones (máxima fecha de aceptación para evitar duplicidad de filas)
    planning_subquery = db.session.query(
        RequestPlanning.requests_id,
        func.max(RequestPlanning.accepted_at).label('max_accepted_at')
    ).group_by(RequestPlanning.requests_id).subquery()

    # Subconsulta para justificaciones de mora formal registradas
    just_subquery = db.session.query(
        RequestJustification.request_id,
        func.count(RequestJustification.id).label('just_count')
    ).filter(
        RequestJustification.justification_type.in_(['RETRASO_ATENCION', 'RETRASO_EJECUCION'])
    ).group_by(RequestJustification.request_id).subquery()

    # Criterio SQL de Mora
    cond_atencion = and_(
        Status.status_code.in_(['STAT-003', 'STAT-004']),
        func.now() - Request.created_at > text("INTERVAL '72 hours'")
    )
    cond_ejecucion = and_(
        Status.status_code == 'STAT-006',
        or_(
            and_(
                planning_subquery.c.max_accepted_at.isnot(None),
                func.now() - planning_subquery.c.max_accepted_at > text("INTERVAL '10 days'")
            ),
            func.now() - Request.created_at > text("INTERVAL '10 days'")
        )
    )

    # 1. Agregación de Contadores Métricos KPI
    kpi_query = db.session.query(
        func.count(Request.id).label('total'),
        func.count(case((just_subquery.c.just_count.is_(None), 1))).label('unjustified'),
        func.count(case((just_subquery.c.just_count > 0, 1))).label('justified')
    ).select_from(Request).join(
        Status, Request.status_id == Status.id
    ).join(
        InstitutionalStaff, Request.institutional_staff_id == InstitutionalStaff.id
    ).join(
        Institution, InstitutionalStaff.institution_id == Institution.id
    ).join(
        Parish, Institution.parish_id == Parish.id
    ).join(
        Municipality, Parish.municipality_id == Municipality.id
    ).outerjoin(
        planning_subquery, planning_subquery.c.requests_id == Request.id
    ).outerjoin(
        just_subquery, just_subquery.c.request_id == Request.id
    ).filter(
        Request.historical == False,
        or_(cond_atencion, cond_ejecucion)
    )

    if state_id:
        kpi_query = kpi_query.filter(Municipality.state_id == state_id)

    kpi_res = kpi_query.first()
    kpis = {
        'total': kpi_res.total if kpi_res and kpi_res.total else 0,
        'unjustified': kpi_res.unjustified if kpi_res and kpi_res.unjustified else 0,
        'justified': kpi_res.justified if kpi_res and kpi_res.justified else 0,
    }

    # 2. Consulta Paginada de Solicitudes en Mora con JoinedLoad
    query = Request.query.join(
        Status, Request.status_id == Status.id
    ).join(
        InstitutionalStaff, Request.institutional_staff_id == InstitutionalStaff.id
    ).join(
        Institution, InstitutionalStaff.institution_id == Institution.id
    ).join(
        Parish, Institution.parish_id == Parish.id
    ).join(
        Municipality, Parish.municipality_id == Municipality.id
    ).join(
        State, Municipality.state_id == State.id
    ).join(
        Training, Request.training_id == Training.id
    ).outerjoin(
        planning_subquery, planning_subquery.c.requests_id == Request.id
    ).outerjoin(
        just_subquery, just_subquery.c.request_id == Request.id
    ).filter(
        Request.historical == False,
        or_(cond_atencion, cond_ejecucion)
    ).options(
        joinedload(Request.status),
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution)
            .joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.person),
        joinedload(Request.attended_by).joinedload(User.person),
        joinedload(Request.plannings),
        joinedload(Request.justifications).joinedload(RequestJustification.reason)
    )

    if state_id:
        query = query.filter(Municipality.state_id == state_id)

    if justification_status == 'unjustified':
        query = query.filter(just_subquery.c.just_count.is_(None))
    elif justification_status == 'justified':
        query = query.filter(just_subquery.c.just_count > 0)

    if search:
        search_clean = search.strip()
        if search_clean:
            search_pattern = f"%{search_clean}%"
            query = query.filter(
                or_(
                    Request.request_code.ilike(search_pattern),
                    Institution.institution_name.ilike(search_pattern),
                    Training.name.ilike(search_pattern)
                )
            )

    # Ordenamiento: Casos sin justificar (más críticos) primero, luego por mayor antigüedad
    query = query.order_by(
        case((just_subquery.c.just_count.is_(None), 1), else_=2).asc(),
        Request.created_at.asc()
    )

    safe_page = max(1, page) if isinstance(page, int) else 1
    safe_per_page = min(max(1, per_page), 50) if isinstance(per_page, int) else 10

    pagination = query.paginate(page=safe_page, per_page=safe_per_page, error_out=False)

    # Clasificación y enriquecimiento dinámico de cada registro
    for req in pagination.items:
        created_at = req.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        elif not created_at:
            created_at = now_dt

        # Determinar si existe descargo registrado
        has_just = any(
            j.justification_type in ('RETRASO_ATENCION', 'RETRASO_EJECUCION')
            for j in req.justifications
        )
        req.has_justification = has_just

        # Fase de mora y cómputo de demora
        status_code = req.status.status_code if req.status else ''
        if status_code in ('STAT-003', 'STAT-004'):
            req.mora_phase = "Atención Inicial"
            delta_hours = max(0.0, (now_dt - created_at).total_seconds() / 3600.0)
            days = int(delta_hours // 24)
            req.delay_days = days
            req.delay_text = f"+{days} días sin atender" if days >= 3 else "Límite ANS superado"
        else:
            req.mora_phase = "Ejecución Presencial"
            accepted_at = None
            if req.plannings:
                for p in req.plannings:
                    if p.accepted_at:
                        accepted_at = p.accepted_at
                        if accepted_at.tzinfo is None:
                            accepted_at = accepted_at.replace(tzinfo=timezone.utc)
                        break
            ref_dt = accepted_at if accepted_at else created_at
            days_proc = max(0, (now_dt - ref_dt).days)
            req.delay_days = days_proc
            req.delay_text = f"+{days_proc} días en proceso"

    return {
        "kpis": kpis,
        "pagination": pagination,
        "requests": pagination.items
    }


def get_request_justification_detail(request_id: int) -> dict | None:
    """
    Retorna el detalle serializado del descargo operativo asociado a una solicitud demorada
    (RETRASO_ATENCION o RETRASO_EJECUCION).
    """
    req = Request.query.options(
        joinedload(Request.status),
        joinedload(Request.attended_by).joinedload(User.person),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution)
            .joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
        joinedload(Request.justifications).joinedload(RequestJustification.reason),
        joinedload(Request.tracking_steps)
    ).get(request_id)

    if not req:
        return None

    delay_just = None
    for j in req.justifications:
        if j.justification_type in ('RETRASO_ATENCION', 'RETRASO_EJECUCION'):
            delay_just = j
            break

    if not delay_just:
        return None

    inst_name = "Plantel Educativo"
    state_name = "Nacional"
    try:
        if req.institutional_staff and req.institutional_staff.institution:
            inst_name = req.institutional_staff.institution.institution_name
            state_name = req.institutional_staff.institution.parish.municipality.state.name
    except (AttributeError, IndexError):
        pass

    if req.attended_by and req.attended_by.person:
        p = req.attended_by.person
        submitted_by = f"{p.first_name} {p.last_name} (Admin Estadal {state_name})"
    else:
        submitted_by = f"Administración Estadal ({state_name})"

    # Obtener marca temporal del descargo desde tracking o fechas del expediente
    just_dt = None
    if req.tracking_steps:
        for t in reversed(req.tracking_steps):
            msg = (t.messages or "").lower()
            if "justificaci" in msg or "descargo" in msg:
                just_dt = t.created_at
                break
    if not just_dt:
        just_dt = req.updated_at or req.created_at or datetime.now()
    created_at_str = just_dt.strftime("%d/%m/%Y %I:%M %p")

    reason_name = delay_just.reason.name if delay_just.reason else "Causa Operativa Justificada"

    return {
        "request_code": req.request_code,
        "institution_name": inst_name,
        "reason_name": reason_name,
        "submitted_by": submitted_by,
        "created_at": created_at_str,
        "justification_text": delay_just.justification,
        "justification_type": delay_just.justification_type
    }


def demand_delay_response(request_id: int, super_admin_user) -> tuple[bool, str, int]:
    """
    Registra la exigencia formal al operador responsable por vulneración del ANS.
    Bloqueado estrictamente a una sola exigencia por solicitud para evitar spam.
    Sin despacho de bitácora ni notificaciones automáticas conforme a directriz.
    """
    from app.models.request_tracking_model import RequestTracking

    req = Request.query.options(
        joinedload(Request.status),
        joinedload(Request.attended_by).joinedload(User.person),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution)
            .joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
        joinedload(Request.plannings),
        joinedload(Request.justifications),
        joinedload(Request.trackings)
    ).get(request_id)

    if not req:
        return False, "La solicitud indicada no existe.", 404

    if req.historical:
        return False, "La solicitud es histórica y no admite acciones disciplinarias.", 422

    now_dt = datetime.now(timezone.utc)
    created_at = req.created_at
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    elif not created_at:
        created_at = now_dt

    status_code = req.status.status_code if req.status else ''
    is_delayed = False

    if status_code in ('STAT-003', 'STAT-004'):
        delta_hours = (now_dt - created_at).total_seconds() / 3600.0
        if delta_hours > 72.0:
            is_delayed = True
    elif status_code == 'STAT-006':
        accepted_at = None
        if req.plannings:
            for p in req.plannings:
                if p.accepted_at:
                    accepted_at = p.accepted_at
                    if accepted_at.tzinfo is None:
                        accepted_at = accepted_at.replace(tzinfo=timezone.utc)
                    break
        ref_dt = accepted_at if accepted_at else created_at
        days_proc = (now_dt - ref_dt).days
        if days_proc > 10:
            is_delayed = True

    if not is_delayed:
        return False, "El expediente se encuentra dentro de los plazos reglamentarios o no aplica intimación.", 422

    has_just = any(
        j.justification_type in ('RETRASO_ATENCION', 'RETRASO_EJECUCION', 'RETRASO', 'REPROGRAMACION')
        for j in req.justifications
    )
    if has_just:
        return False, "El expediente ya cuenta con un descargo formal consignado.", 422

    # Bloqueo estricto: Una sola exigencia por solicitud para evitar spam
    existing_demand = any(
        'exigencia formal' in (t.messages or '').lower()
        for t in req.trackings
    )
    if existing_demand:
        return False, "Ya se ha emitido una exigencia formal previa para este expediente. Debe esperar la respuesta.", 422

    # Trazabilidad en sages.request_trackings
    tracking = RequestTracking(
        request_id=req.id,
        user_id=super_admin_user.id,
        messages="La Gerencia General (Super Administrador) ha emitido una exigencia formal de justificación operativa por vencimiento de plazos normativos."
    )
    db.session.add(tracking)
    db.session.commit()

    return True, "Exigencia formal registrada exitosamente en el expediente.", 200


# ---------------------------------------------------------------------------
# SLA Gate: Justificación Obligatoria de Retraso (Modal Bloqueante)
# ---------------------------------------------------------------------------

def get_delay_reasons() -> list:
    """
    Retorna el catálogo de razones válidas para justificación de mora ANS.
    Filtra prioritariamente las razones con prefijo 'RSL-' (Retraso SLA).
    """
    from app.models.reason_model import Reason
    reasons = Reason.query.filter(
        Reason.reason_code.like('RSL-%')
    ).order_by(Reason.name.asc()).all()

    # Fallback: Si no existen razones específicas RSL-, devolver todas
    if not reasons:
        reasons = Reason.query.order_by(Reason.name.asc()).all()

    return [{'id': r.id, 'code': r.reason_code, 'name': r.name} for r in reasons]


def submit_delay_justification(
    request_id: int,
    admin_user,
    reason_id: int,
    justification_text: str
) -> tuple[bool, str, int]:
    """
    Registra el descargo formal de mora ANS (SLA Gate) para una solicitud bloqueada.

    Reglas de Negocio:
      - Solo aplica a solicitudes con bloqueo activo ANS.
      - El texto del descargo debe tener mínimo 20 caracteres.
      - La razón debe existir en el catálogo sages.reasons.
      - Determina el tipo automáticamente: RETRASO_ATENCION o RETRASO_EJECUCION.
      - Persiste en sages.request_justifications y genera tracking (sin bitácora ni notificaciones).
      - Bloquea spam: solo permite una justificación por expediente.
      - Retorna (success: bool, message: str, http_status: int).
    """
    from app.models.reason_model import Reason
    from app.models.request_tracking_model import RequestTracking

    # ── 1. Validaciones de Entrada ──────────────────────────────────────────
    if not justification_text or len(justification_text.strip()) < 20:
        return False, "El descargo debe contener al menos 20 caracteres.", 400

    justification_text = justification_text.strip()

    # ── 2. Cargar Solicitud con Carga Ansiosa ───────────────────────────────
    req = Request.query.options(
        joinedload(Request.status),
        joinedload(Request.justifications),
        joinedload(Request.plannings),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution)
    ).get(request_id)

    if not req:
        return False, "La solicitud indicada no existe.", 404

    if req.historical:
        return False, "La solicitud es histórica y no admite justificaciones operativas.", 422

    # ── 3. Verificar Estado de Bloqueo ANS ─────────────────────────────────
    vzla_tz = timezone(timedelta(hours=-4))
    now_local = datetime.now(vzla_tz)
    status_code = req.status.status_code if req.status else ''

    has_delay_block = False
    justification_type = None

    if status_code == 'STAT-003':
        if req.created_at:
            hours_diff = (now_local - req.created_at.astimezone(vzla_tz)).total_seconds() / 3600
            if hours_diff > 72:
                has_delay_block = True
                justification_type = 'RETRASO_ATENCION'

    elif status_code in ('STAT-004', 'STAT-005', 'STAT-006'):
        if req.updated_at:
            hours_diff = (now_local - req.updated_at.astimezone(vzla_tz)).total_seconds() / 3600
            if hours_diff > 240:
                has_delay_block = True
                justification_type = 'RETRASO_EJECUCION'

    # Verificar si ya existe justificación de retraso previa (Anti-spam estricto)
    already_justified = any(
        j.justification_type in ('RETRASO_ATENCION', 'RETRASO_EJECUCION', 'RETRASO', 'REPROGRAMACION')
        for j in req.justifications
    )

    if already_justified:
        return False, "Este expediente ya cuenta con un descargo formal registrado.", 422

    if not has_delay_block:
        return False, "Este expediente no presenta bloqueo ANS activo que requiera justificación.", 422

    # ── 4. Validar Razón ────────────────────────────────────────────────────
    reason = Reason.query.get(reason_id)
    if not reason:
        return False, "La razón seleccionada no es válida.", 400

    # ── 5. Transacción Atómica ──────────────────────────────────────────────
    try:
        # 5a. Persistir Justificación
        new_just = RequestJustification(
            request_id=req.id,
            reason_id=reason.id,
            justification_type=justification_type,
            justification=justification_text
        )
        db.session.add(new_just)

        # 5b. Tracking de Trazabilidad en el Expediente
        admin_name = "Administrador"
        if admin_user and hasattr(admin_user, 'person') and admin_user.person:
            admin_name = f"{admin_user.person.first_name} {admin_user.person.last_name}"

        tracking = RequestTracking(
            request_id=req.id,
            user_id=admin_user.id,
            messages=(
                f"Descargo formal de justificación registrado por {admin_name}. "
                f"Razón: {reason.name}. Tipo: {justification_type}."
            )
        )
        db.session.add(tracking)

        db.session.commit()
        return True, "Descargo registrado correctamente. El bloqueo operativo ha sido levantado.", 200

    except Exception as e:
        db.session.rollback()
        import logging
        logging.getLogger(__name__).error(
            f"Error al registrar justificación SLA para request_id={request_id}: {e}"
        )
        return False, "Error interno al registrar el descargo. Intente nuevamente.", 500
