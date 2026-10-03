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
from app.models.training_module_model import TrainingModule
from app.models.request_planning_model import RequestPlanning
from app.models.request_justification_model import RequestJustification

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
    Dispara la intimación coercitiva multicanal (UI DANGER, correo asíncrono, bitácoras)
    al operador responsable por vulneración del ANS.
    """
    from app.models.role_model import Role
    from app.models.role_user_model import RoleUser
    from app.models.request_tracking_model import RequestTracking
    from app.models.notification_model import Notification
    from app.notifications.services import NotificationService
    from app.binnacle.services import BinnacleService
    from app.utils.email_utils import send_delay_demand_email

    req = Request.query.options(
        joinedload(Request.status),
        joinedload(Request.attended_by).joinedload(User.person),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution)
            .joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
        joinedload(Request.plannings),
        joinedload(Request.justifications)
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
    phase_name = ""
    delay_info = ""

    if status_code in ('STAT-003', 'STAT-004'):
        delta_hours = (now_dt - created_at).total_seconds() / 3600.0
        if delta_hours > 72.0:
            is_delayed = True
            days = int(delta_hours // 24)
            phase_name = "Atención Inicial (Vencimiento ANS 72h)"
            delay_info = f"+{days} días sin atención inicial"
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
            phase_name = "Ejecución Presencial (Vencimiento ANS 10 días)"
            delay_info = f"+{days_proc} días continuos en ejecución"

    if not is_delayed:
        return False, "El expediente se encuentra dentro de los plazos reglamentarios o no aplica intimación.", 422

    has_just = any(
        j.justification_type in ('RETRASO_ATENCION', 'RETRASO_EJECUCION')
        for j in req.justifications
    )
    if has_just:
        return False, "El expediente ya cuenta con un descargo formal consignado.", 422

    inst_name = "Plantel Educativo"
    state_id = None
    if req.institutional_staff and req.institutional_staff.institution:
        inst_name = req.institutional_staff.institution.institution_name
        try:
            state_obj = req.institutional_staff.institution.parish.municipality.state
            state_id = state_obj.id
        except AttributeError:
            pass

    # Identificar destinatarios
    recipients = []
    if req.attended_by:
        recipients.append(req.attended_by)
    else:
        all_state_admins = User.query.join(RoleUser).join(Role).filter(Role.name == 'state_admin').all()
        for sa in all_state_admins:
            if sa.person and sa.person.company_staff:
                try:
                    staff_state = sa.person.company_staff[0].place.parish.municipality.state_id
                    if state_id and staff_state == state_id:
                        recipients.append(sa)
                except (AttributeError, IndexError):
                    pass
        if not recipients:
            recipients = all_state_admins

    # 1. Notificación Campana UI (Canal 1 - DANGER)
    for recipient in recipients:
        try:
            notif = Notification(
                notification_code=NotificationService.generate_notification_code(),
                user_id=recipient.id,
                type='DANGER',
                event_code='SOLICITUD_DEMORADA',
                title="REQUERIMIENTO URGENTE: Justificación de Retraso Exigida",
                message=f"La Gerencia General exige descargo formal inmediato para el expediente {req.request_code} ({inst_name}).",
                redirect_url='/requests/process-inbox',
                action_text='Atender Expediente',
                extra_data={'request_code': req.request_code, 'institution_name': inst_name}
            )
            db.session.add(notif)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error despachando notificación campana a user_id {recipient.id}: {e}")

    # 2. Correo Electrónico Institucional Asíncrono (Canal 2)
    for recipient in recipients:
        if recipient.person and recipient.person.email:
            rec_name = f"{recipient.person.first_name} {recipient.person.last_name}"
            send_delay_demand_email(
                to_email=recipient.person.email,
                recipient_name=rec_name,
                request_code=req.request_code,
                institution_name=inst_name,
                delay_info=delay_info,
                phase_name=phase_name
            )

    # 3. Trazabilidad en sages.request_trackings
    tracking = RequestTracking(
        request_id=req.id,
        user_id=super_admin_user.id,
        messages="La Gerencia General (Super Administrador) ha emitido una exigencia formal de justificación operativa por vencimiento de plazos normativos."
    )
    db.session.add(tracking)

    # 4. Bitácora Forense (BinnacleService)
    recipient_names = ", ".join([
        f"{r.person.first_name} {r.person.last_name}" if r.person else f"User {r.id}"
        for r in recipients
    ]) if recipients else "Administración Estadal"
    
    BinnacleService.create_log_entry(
        module='Solicitudes',
        action_type='EXIGIR_RESPUESTA_SLA',
        description=f"Exigencia formal de respuesta emitida para trámite {req.request_code} ({inst_name}). Destinatarios intimados: {recipient_names}.",
        target_table='requests',
        record_id=req.id
    )

    db.session.commit()

    return True, "Requerimiento formal despachado exitosamente al operador responsable.", 200


