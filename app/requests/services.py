from datetime import datetime, timezone, timedelta
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

class RequestAlreadyClaimedException(Exception):
    """Excepción lanzada cuando un administrador intenta atender una solicitud que ya fue tomada concurrentemente."""
    pass

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
        from app.utils.qr_generator import generate_verification_token
        new_request = Request(
            request_code=_generate_request_code(),
            institutional_staff_id=institutional_staff_id,
            training_id=training_id,
            description=description.strip(),
            status_id=status_new.id,
            historical=False
        )
        db.session.add(new_request)
        db.session.flush()
        new_request.verification_token = generate_verification_token(new_request.request_code, new_request.id)
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


def get_applicant_request_detail(request_id: int, user_institution_id: int):
    """
    Obtiene el detalle integral de una solicitud para la vista del directivo/solicitante (US-44).
    Aplica carga ansiosa para optimizar el rendimiento y calcula las banderas de visualización
    (fase del stepper de 5 hitos, fecha pautada, facilitador y posibilidad de desistimiento).
    Garantiza el aislamiento institucional: solo retorna si pertenece al user_institution_id.
    """
    from app.models.reason_model import Reason
    from app.models.request_tracking_model import RequestTracking

    req = Request.query.options(
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.status),
        joinedload(Request.institutional_staff)
            .joinedload(InstitutionalStaff.institution)
            .joinedload(Institution.parish)
            .joinedload(Parish.municipality)
            .joinedload(Municipality.state),
        joinedload(Request.attended_by).joinedload(User.person),
        joinedload(Request.plannings),
        joinedload(Request.justifications).joinedload(RequestJustification.reason)
    ).filter(
        Request.id == request_id
    ).first()

    if not req:
        return None

    # Verificación estricta de aislamiento multitenant
    if not req.institutional_staff or req.institutional_staff.institution_id != user_institution_id:
        return None

    # Evaluar si cuenta con fecha confirmada
    planned_record = next((p for p in req.plannings if p.planned_for is not None), None)
    req.planned_date = planned_record.planned_for if planned_record else None
    has_scheduled_date = req.planned_date is not None
    req.has_scheduled_date = has_scheduled_date

    # Mapeo del Stepper de Progreso (5 Fases institucionales)
    # Paso 1: Recibida (STAT-003)
    # Paso 2: En Coordinación (STAT-004 sin fecha acordada)
    # Paso 3: Fecha Pautada (STAT-005 o STAT-004 con fecha agendada)
    # Paso 4: En Ejecución (STAT-006)
    # Paso 5: Culminada (STAT-007)
    status_code = req.status.status_code if req.status else ''
    
    if status_code == 'STAT-003':
        req.stepper_step = 1
    elif status_code == 'STAT-004' and not has_scheduled_date:
        req.stepper_step = 2
    elif status_code == 'STAT-005' or (status_code == 'STAT-004' and has_scheduled_date):
        req.stepper_step = 3
    elif status_code == 'STAT-006':
        req.stepper_step = 4
    elif status_code == 'STAT-007':
        req.stepper_step = 5
    elif status_code in ['STAT-008', 'STAT-009', 'STAT-010']:
        # Estados cerrados alternativos
        req.stepper_step = 1
    else:
        req.stepper_step = 1

    # Regla de desistimiento voluntario justificado (solo STAT-003 o STAT-004 sin fecha pautada)
    req.can_cancel = (
        status_code == 'STAT-003' or 
        (status_code == 'STAT-004' and not has_scheduled_date)
    ) and not req.historical

    # Si se encuentra cancelada, extraer la justificación registrada (del solicitante o del admin)
    req.cancellation_justification = None
    if status_code == 'STAT-009' or req.historical:
        for just in req.justifications:
            if just.justification_type in ('CANCELACION_SOLICITANTE', 'CANCELACION_ADMIN'):
                req.cancellation_justification = just
                break

    # Cargar cronología estructurada para la bitácora transversal
    req.timeline_steps = get_request_timeline(request_id)

    return req


def cancel_training_request(request_id: int, user: User, reason_id: int, justification_text: str) -> tuple[bool, str, int]:
    """
    Procesa la cancelación motivada e irreversible de una solicitud (US-44).
    Implementación simétrica: soporta al Solicitante (etapas preliminares, mín. 10 caracteres)
    y al Administrador Estadal / Super Administrador (etapas operativas, mín. 20 caracteres).
    Aplica bloqueo pesimista (with_for_update), inmutabilidad FSM, trazabilidad en tracking y binnacle.
    Retorna (éxito: bool, mensaje: str, código_http: int).
    """
    from app.models.reason_model import Reason
    from app.models.request_tracking_model import RequestTracking
    from app.binnacle.services import BinnacleService
    from app.binnacle.types import AuditAction, AuditStatus, AuditModule
    from app.notifications.services import NotificationService
    from app.notifications.enums import NotificationEvent
    from app.utils.email_utils import send_request_cancelled_email


    if not user:
        return False, "Usuario no autenticado o sesión inválida.", 403

    # Determinar roles del usuario
    user_roles = [assoc.role.name for assoc in user.roles_assoc] if user and user.roles_assoc else []
    is_super_admin = 'super_admin' in user_roles
    is_state_admin = 'state_admin' in user_roles
    is_admin = is_super_admin or is_state_admin
    is_applicant = 'applicant' in user_roles

    if not (is_admin or is_applicant):
        return False, "Usuario no autorizado para gestionar cancelaciones de solicitudes.", 403

    # 1. Bloqueo pesimista de fila en BD (Pessimistic Locking)
    req = db.session.query(Request).filter(Request.id == request_id).with_for_update().first()

    if not req:
        db.session.rollback()
        return False, "Solicitud no encontrada.", 404

    # 2. Protección de Inmutabilidad FSM (Expedientes completados, históricos o ya cancelados)
    current_status = req.status.status_code if req.status else ''
    if current_status == 'STAT-007':
        db.session.rollback()
        return False, "Operación rechazada: No es posible cancelar una solicitud que ya ha sido Completada (STAT-007).", 422

    if req.historical or current_status in ('STAT-008', 'STAT-009'):
        db.session.rollback()
        return False, "Este expediente ya se encuentra cerrado e histórico y no admite modificaciones.", 422

    clean_justification = (justification_text or '').strip()

    # 3. Bifurcación por Actor: Reglas de Fase, Aislamiento y Longitud
    if is_admin:
        # Aislamiento territorial para Administrador Estadal
        if is_state_admin and not is_super_admin:
            admin_state_id = get_admin_state_id(user)
            try:
                req_state_id = req.institutional_staff.institution.parish.municipality.state_id
            except (AttributeError, IndexError):
                req_state_id = None

            if not admin_state_id or req_state_id != admin_state_id:
                db.session.rollback()
                return False, "Acceso denegado: El expediente pertenece a otra jurisdicción territorial.", 403

        # Fases operativas permitidas para Admin (STAT-003, STAT-004, STAT-005, STAT-006)
        if current_status not in ['STAT-003', 'STAT-004', 'STAT-005', 'STAT-006']:
            db.session.rollback()
            return False, f"La solicitud no se encuentra en una fase que admita cancelación administrativa (Estado actual: {req.status.status_name if req.status else current_status}).", 422

        # Longitud mínima de justificación (mín. 20 caracteres)
        if len(clean_justification) < 20:
            db.session.rollback()
            return False, "La justificación administrativa debe contener al menos 20 caracteres.", 400

        justification_type = 'CANCELACION_ADMIN'

    elif is_applicant:
        # Aislamiento institucional para Solicitante
        if not user.person or not user.person.institutional_staff:
            db.session.rollback()
            return False, "Usuario no autorizado o sin vinculación institucional válida.", 403

        user_institution_id = user.person.institutional_staff[0].institution_id
        if not req.institutional_staff or req.institutional_staff.institution_id != user_institution_id:
            db.session.rollback()
            return False, "Acceso denegado: El requerimiento no pertenece a su institución educativa.", 403

        # Fases preliminares permitidas para Solicitante (STAT-003, STAT-004 sin fecha pautada)
        if current_status not in ['STAT-003', 'STAT-004']:
            db.session.rollback()
            return False, "Jornada agendada o en ejecución. Para cancelaciones comuníquese con la Coordinación Estadal de UREE.", 422

        has_scheduled_date = any(p.planned_for is not None for p in req.plannings)
        if has_scheduled_date:
            db.session.rollback()
            return False, "Jornada agendada o en ejecución. Para cancelaciones comuníquese con la Coordinación Estadal de UREE.", 422

        # Longitud mínima de justificación (mín. 10 caracteres)
        if len(clean_justification) < 10:
            db.session.rollback()
            return False, "La justificación explicativa debe contener al menos 10 caracteres.", 400

        justification_type = 'CANCELACION_SOLICITANTE'
    else:
        db.session.rollback()
        return False, "Perfil de usuario no autorizado.", 403

    # 4. Validar existencia del motivo de catálogo
    reason = Reason.query.get(reason_id)
    if not reason:
        db.session.rollback()
        return False, "El motivo de cancelación seleccionado no existe en el catálogo oficial.", 400

    # 5. Obtener estado Cancelado (STAT-009)
    status_cancelled = Status.query.filter_by(status_code='STAT-009').first()
    if not status_cancelled:
        db.session.rollback()
        return False, "Error interno: Estado STAT-009 no encontrado en el sistema.", 500

    try:
        now_utc = datetime.now(timezone.utc)

        # 6. Registrar en sages.request_justifications (sin user_id por esquema)
        justification = RequestJustification(
            request_id=req.id,
            reason_id=reason.id,
            justification_type=justification_type,
            justification=clean_justification
        )
        db.session.add(justification)

        # 7. Actualizar sages.requests
        req.status_id = status_cancelled.id
        req.finished_at = now_utc
        req.updated_at = now_utc
        req.historical = True

        # 8. Asentar traza institucional en sages.request_trackings
        actor_name = f"{user.person.first_name} {user.person.last_name}".strip() if user.person else user.username
        if justification_type == 'CANCELACION_ADMIN':
            tracking_message = (
                f"La Coordinación de CORPOELEC ({actor_name}) ha cancelado administrativamente la solicitud. "
                f"Motivo: {reason.name}. Detalle: {clean_justification}"
            )
        else:
            tracking_message = (
                f"El representante del plantel educativo ({actor_name}) ha cancelado la solicitud. "
                f"Motivo: {reason.name}. Detalle: {clean_justification}"
            )

        tracking = RequestTracking(
            request_id=req.id,
            user_id=user.id,
            messages=tracking_message,
            created_at=now_utc
        )
        db.session.add(tracking)

        # 9. Asentar auditoría transversal en sages.binnacle
        BinnacleService.create_log_entry(
            module=AuditModule.REQUESTS.value,
            action_type=AuditAction.CAMBIO_ESTATUS.value,
            description=f"Solicitud {req.request_code} cancelada ({justification_type}). Motivo: {reason.name}",
            target_table='sages.requests',
            record_id=req.id,
            old_values={'status_code': current_status, 'historical': False},
            new_values={'status_code': 'STAT-009', 'historical': True},
            status=AuditStatus.MODIFICADO.value,
            session_instance=db.session
        )

        # 10. Notificación y correo asíncrono a la contraparte
        try:
            inst_name = req.institutional_staff.institution.institution_name if req.institutional_staff and req.institutional_staff.institution else "Plantel Educativo"
            training_name = req.training.name if req.training else "Formación Solicitada"

            context = {
                "institution_name": inst_name,
                "training_name": training_name,
                "reason_name": reason.name,
                "justification": clean_justification
            }

            if justification_type == 'CANCELACION_SOLICITANTE':
                # Notificar a los administradores / operador asignado
                target_user = None
                if req.attended_by_id and req.attended_by:
                    target_user = req.attended_by
                    NotificationService.notify_user(
                        user_id=req.attended_by_id,
                        event=NotificationEvent.REQUEST_CANCELLED_BY_APPLICANT,
                        context=context,
                        db_session=db.session
                    )
                else:
                    notifications = NotificationService.notify_role(
                        role_name='state_admin',
                        event=NotificationEvent.REQUEST_CANCELLED_BY_APPLICANT,
                        context=context,
                        db_session=db.session
                    )
                    if notifications:
                        target_user = User.query.get(notifications[0].user_id)

                admin_email = target_user.person.email if target_user and target_user.person else None
                if admin_email:
                    admin_name = f"{target_user.person.first_name} {target_user.person.last_name}".strip() if target_user.person else "Administrador"
                    send_request_cancelled_email(
                        to_email=admin_email,
                        recipient_name=admin_name,
                        institution_name=inst_name,
                        request_code=req.request_code,
                        training_name=training_name,
                        reason_name=reason.name,
                        justification=clean_justification,
                        is_admin_cancellation=False
                    )

            else:  # CANCELACION_ADMIN
                # Notificar a los usuarios afiliados al plantel educativo
                if req.institutional_staff and req.institutional_staff.institution_id:
                    NotificationService.notify_institution_affiliates(
                        institution_id=req.institutional_staff.institution_id,
                        event=NotificationEvent.REQUEST_CANCELLED_BY_ADMIN,
                        context=context,
                        redirect_url=f"/requests/my-requests/{req.id}",
                        action_text="Ver Expediente",
                        db_session=db.session
                    )

                # Correo al representante del requerimiento
                applicant_email = req.institutional_staff.person.email if req.institutional_staff and req.institutional_staff.person else None
                if applicant_email:
                    applicant_name = f"{req.institutional_staff.person.first_name} {req.institutional_staff.person.last_name}".strip() if req.institutional_staff.person else "Representante Institucional"
                    send_request_cancelled_email(
                        to_email=applicant_email,
                        recipient_name=applicant_name,
                        institution_name=inst_name,
                        request_code=req.request_code,
                        training_name=training_name,
                        reason_name=reason.name,
                        justification=clean_justification,
                        is_admin_cancellation=True
                    )

        except Exception as notif_err:
            import logging
            logging.getLogger(__name__).warning(f"No se pudo despachar la notificación de cancelación: {notif_err}")

        # 11. Confirmación de transacción
        db.session.commit()

        success_msg = (
            "La solicitud ha sido cancelada formalmente y sellada como expediente histórico."
            if is_admin else
            "Su solicitud ha sido cancelada exitosamente y trasladada a su historial."
        )
        return True, success_msg, 200

    except Exception as e:
        db.session.rollback()
        import logging
        logging.getLogger(__name__).error(f"Error procesando cancelación de solicitud {req.request_code}: {e}")
        return False, "Ocurrió un error interno en la base de datos al procesar la cancelación.", 500


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
    from app.models.reason_model import Reason
    from app.models.request_tracking_model import RequestTracking

    req = Request.query.options(
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.person),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality),
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.status),
        joinedload(Request.attended_by),
        joinedload(Request.plannings),
        joinedload(Request.justifications).joinedload(RequestJustification.reason),
        joinedload(Request.evidences),
        joinedload(Request.tracking_steps).joinedload(RequestTracking.user).joinedload(User.person)
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

    req.closure_alert = check_closure_spam_alert(req)

    # Evaluación de permisos y extracción de justificación para cancelación en vista Admin (US-44)
    req.can_admin_cancel = (
        status_code in ['STAT-003', 'STAT-004', 'STAT-005', 'STAT-006']
        and not req.historical
    )
    req.cancellation_justification = None
    if status_code == 'STAT-009' or req.historical:
        for just in req.justifications:
            if just.justification_type in ('CANCELACION_ADMIN', 'CANCELACION_SOLICITANTE'):
                req.cancellation_justification = just
                break

    return req

# Bloque Administrador Estadal (Atención y Asignación nominal)
def claim_and_attend_request(request_id: int, admin_user) -> tuple[bool, str, dict]:
    """
    Toma propiedad nominal de una solicitud.
    Ejecuta un bloqueo pesimista en base de datos para prevenir colisiones concurrentes.
    Transiciona a STAT-004 (Pendiente), instancia request_plannings y deja traza.
    """
    from app.models.request_tracking_model import RequestTracking
    
    # Iniciar la transacción y bloquear la fila específica (Pessimistic Locking)
    req = db.session.query(Request).filter(Request.id == request_id).with_for_update().first()
    
    if not req:
        return False, "Solicitud no encontrada.", {}
    # Comprobar que sea el estado correcto
    if req.status.status_code != 'STAT-003':
        return False, f"La solicitud no se encuentra en estado Nuevo (Actual: {req.status.status_code}).", {}
    # Comprobar si ya fue asignada en un hilo concurrente
    if req.attended_by_id is not None:
        db.session.rollback()
        raise RequestAlreadyClaimedException("Esta solicitud ya ha sido asumida por otro operador de la sede.")
    # Consultar el estado Pendiente
    status_pending = Status.query.filter_by(status_code='STAT-004').first()
    if not status_pending:
        db.session.rollback()
        return False, "Error interno: Estado STAT-004 no encontrado en catálogo.", {}
    try:
        # 1. Asignar operador y actualizar estado
        req.attended_by_id = admin_user.id
        req.status_id = status_pending.id
        req.updated_at = datetime.now(timezone.utc)
        
        # 2. Instanciación satélite diferida de RequestPlanning
        accepted_at = datetime.now(timezone.utc)
        planning = RequestPlanning(
            requests_id=req.id,
            accepted_at=accepted_at,
            acceptance_deadline=req.created_at + timedelta(hours=72),
            execution_deadline=accepted_at + timedelta(days=10)
        )
        db.session.add(planning)
        
        # 3. Traza automática institucional en Bitácora
        admin_name = f"{admin_user.person.first_name} {admin_user.person.last_name}"
        tracking_msg = (
            f"Solicitud asignada al Administrador {admin_name}. "
            f"El Administrador encargado se pondrá en contacto directo con su institución "
            f"para coordinar requerimientos logísticos, espacio, cantidad estimada de "
            f"participantes y confirmar la fecha definitiva de la jornada."
        )
        tracking = RequestTracking(
            request_id=req.id,
            user_id=admin_user.id,
            messages=tracking_msg
        )
        db.session.add(tracking)
        
        # 4. Commit Atómico Completo
        db.session.commit()
        
        # 5. Despacho de Correo Asíncrono
        try:
            from app.utils.email_utils import send_request_claimed_email
            
            # Navegar hacia la Persona (Solicitante) a través de InstitutionalStaff
            applicant_person = req.institutional_staff.person
            applicant_email = applicant_person.email
            applicant_name = f"{applicant_person.first_name} {applicant_person.last_name}"
            
            # Extraer institución
            inst_name = req.institutional_staff.institution.institution_name
                
            send_request_claimed_email(
                to_email=applicant_email,
                full_name=applicant_name,
                institution_name=inst_name,
                request_code=req.request_code,
                admin_name=admin_name
            )
        except Exception as email_e:
            import logging
            logging.error(f"No se pudo enviar el correo de asignación: {email_e}")
        
        return True, "Solicitud asignada exitosamente.", {
            "status_code": status_pending.status_code,
            "status_name": status_pending.status_name,
            "operator_name": admin_name
        }
        
    except Exception as e:
        db.session.rollback()
        return False, f"Error transaccional en asignación: {str(e)}", {}

# ---------------------------------------------------------------------------
# Planificar Formación
# ---------------------------------------------------------------------------

def plan_training_session(request_id: int, planned_date, notes: str, admin_user, delay_reason_id: int = None, delay_justification: str = None) -> tuple[bool, str, dict]:
    """
    Planifica la fecha de una jornada formativa (US-41).
    Valida la titularidad operativa, evalúa los límites de ANS, y transiciona a STAT-005.
    Registra el hito en la bitácora y dispara la notificación asíncrona.
    """
    from app.models.request_tracking_model import RequestTracking
    
    # 1. Recuperar la solicitud con bloqueo pesimista
    req = db.session.query(Request).filter(Request.id == request_id).with_for_update().first()
    
    if not req:
        return False, "Solicitud no encontrada.", {}

    # 2. Validación Defensiva: Titularidad Operativa
    if req.attended_by_id != admin_user.id:
        db.session.rollback()
        return False, "Operación denegada. Usted no es el operador asignado a esta solicitud.", {}

    # 3. Validación de Estado FSM (Máquina de Estados manual)
    if req.status.status_code != 'STAT-004':
        db.session.rollback()
        return False, f"Transición ilegal. La solicitud debe estar en estado 'Pendiente' (Actual: {req.status.status_code}).", {}

    # 4. Recuperar la planificación vinculada
    planning = RequestPlanning.query.filter_by(requests_id=req.id).first()
    if not planning:
        db.session.rollback()
        return False, "Error de integridad: La solicitud no posee un registro de planificación asociado.", {}

    try:
        # 5. Evaluación Transaccional del ANS (SLA)
        is_exceeded = False
        time_exceeded = 0
        deadline_date = planning.execution_deadline.date() if hasattr(planning.execution_deadline, 'date') else planning.execution_deadline
        if deadline_date and planned_date > deadline_date:
            is_exceeded = True
            time_exceeded = (planned_date - deadline_date).days
            
            # Defensive check en backend (Doble Capa)
            if not delay_reason_id or not delay_justification:
                db.session.rollback()
                return False, "La fecha supera el límite de gestión ANS (10 días). Se requiere seleccionar un motivo y una justificación.", {}
            
            # Registrar Justificación de Retraso
            justification_record = RequestJustification(
                request_id=req.id,
                reason_id=delay_reason_id,
                justification_type='RETRASO_EJECUCION',
                justification=delay_justification.strip()
            )
            db.session.add(justification_record)

        # 6. Actualizar modelo de Planificación
        planning.planned_for = planned_date
        planning.original_planned_for = planned_date
        planning.is_exceeded = is_exceeded
        if is_exceeded:
            planning.time_exceeded = time_exceeded

        # 7. Avanzar el Estado de la Solicitud
        status_planned = Status.query.filter_by(status_code='STAT-005').first()
        if not status_planned:
            db.session.rollback()
            return False, "Error interno: Estado STAT-005 no encontrado en catálogo.", {}
            
        req.status_id = status_planned.id
        req.updated_at = datetime.now(timezone.utc)

        # 8. Asiento transversal en Bitácora
        formatted_date = planned_date.strftime("%d/%m/%Y")
        tracking_msg = f"Jornada formativa agendada formalmente para el día {formatted_date}."
        if notes:
            tracking_msg += f" Observaciones: {notes.strip()}"
        if is_exceeded:
            tracking_msg += f" (Notificación de ANS: La fecha supera por {time_exceeded} días el límite establecido)."

        tracking = RequestTracking(
            request_id=req.id,
            user_id=admin_user.id,
            messages=tracking_msg
        )
        db.session.add(tracking)

        # 9. Commit atómico
        db.session.commit()

        # 10. Notificación por Correo Asíncrono
        try:
            from app.utils.email_utils import send_request_planned_email
            applicant_person = req.institutional_staff.person
            applicant_name = f"{applicant_person.first_name} {applicant_person.last_name}"
            inst_name = req.institutional_staff.institution.institution_name
            
            send_request_planned_email(
                to_email=applicant_person.email,
                full_name=applicant_name,
                institution_name=inst_name,
                request_code=req.request_code,
                planned_date=formatted_date,
                notes=notes
            )
        except Exception as email_e:
            import logging
            logging.error(f"Fallo no crítico al despachar correo de planificación: {email_e}")

        return True, "Fecha agendada exitosamente.", {
            "planned_date": formatted_date,
            "status_code": status_planned.status_code,
            "status_name": status_planned.status_name,
            "is_exceeded": is_exceeded
        }

    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Error transaccional en plan_training_session: {str(e)}")
        return False, "Ocurrió un error transaccional al agendar la solicitud.", {}


# ---------------------------------------------------------------------------
# Reprogramar Jornada Formativa (US-42 / SR-F-022)
# ---------------------------------------------------------------------------

def reschedule_training_session(
    request_id: int,
    new_date,
    reason_id: int,
    justification: str,
    admin_user
) -> tuple[bool, str, dict]:
    """
    Modifica la fecha agendada (planned_for) de una solicitud en estado Planificada (STAT-005)
    o En Proceso (STAT-006) por causa mayor debidamente justificada (US-42 / SR-F-022).
    
    Operaciones:
      1. Bloqueo pesimista con verificación de titularidad y estado FSM.
      2. Actualiza sages.request_plannings (planned_for y rescheduled_count += 1, original_planned_for intacto).
      3. Inserta asiento en sages.request_justifications (justification_type='REPROGRAMACION').
      4. Inserta traza indeleble en sages.requests_trackings.
      5. Confirma atómicamente la transacción (commit).
      6. Emite notificación al solicitante y envía correo institucional asíncrono.
    """
    from app.models.request_tracking_model import RequestTracking
    from app.models.request_planning_model import RequestPlanning
    from app.models.request_justification_model import RequestJustification
    from app.models.reason_model import Reason
    from datetime import date as date_cls

    # 1. Recuperar la solicitud con bloqueo pesimista
    req = db.session.query(Request).filter(Request.id == request_id).with_for_update().first()
    if not req:
        return False, "Solicitud no encontrada.", {}

    # 2. Validación de Titularidad Operativa y Permisos
    user_roles = [assoc.role.name for assoc in admin_user.roles_assoc] if admin_user and admin_user.roles_assoc else []
    is_super_admin = 'super_admin' in user_roles

    if not is_super_admin and req.attended_by_id != admin_user.id:
        db.session.rollback()
        return False, "Operación denegada. Solo el operador responsable puede reprogramar esta solicitud.", {}

    # 3. Validación de Estado FSM (Solo STAT-005 o STAT-006)
    if not req.status or req.status.status_code not in ['STAT-005', 'STAT-006']:
        db.session.rollback()
        current_code = req.status.status_code if req.status else 'Desconocido'
        return False, f"Transición ilegal. Solo se pueden reprogramar solicitudes planificadas o en proceso (Actual: {current_code}).", {}

    # 4. Recuperar la planificación satélite asociada
    planning = RequestPlanning.query.filter_by(requests_id=req.id).first()
    if not planning:
        db.session.rollback()
        return False, "Error de integridad: La solicitud no posee un registro de planificación asociado.", {}

    # 5. Validar fecha estrictamente futura en día hábil
    if hasattr(new_date, 'date'):
        parsed_date = new_date.date()
    else:
        parsed_date = new_date

    if parsed_date <= date_cls.today():
        db.session.rollback()
        return False, "La nueva fecha debe ser estrictamente posterior al día de hoy.", {}

    if parsed_date.weekday() >= 5:
        db.session.rollback()
        return False, "La nueva fecha debe ser un día hábil (de lunes a viernes).", {}

    # 6. Validar motivo catalogado en sages.reasons
    reason = Reason.query.get(reason_id)
    if not reason:
        db.session.rollback()
        return False, "El motivo de reprogramación seleccionado no existe en el catálogo oficial.", {}

    # 7. Validar justificación técnica mínima
    clean_justification = (justification or '').strip()
    if len(clean_justification) < 20:
        db.session.rollback()
        return False, "La justificación explicativa debe contener al menos 20 caracteres válidos.", {}

    try:
        # 8. Modificar entidad satélite RequestPlanning
        # Regla de Auditoría: original_planned_for se conserva intacto
        planning.planned_for = parsed_date
        planning.rescheduled_count = (planning.rescheduled_count or 0) + 1

        # 9. Asentar registro en sages.request_justifications (Tipo REPROGRAMACION)
        justification_record = RequestJustification(
            request_id=req.id,
            reason_id=reason.id,
            justification_type='REPROGRAMACION',
            justification=clean_justification
        )
        db.session.add(justification_record)

        # 10. Asentar hito transversal en sages.requests_trackings
        formatted_date = parsed_date.strftime("%d/%m/%Y")
        actor_name = f"{admin_user.person.first_name} {admin_user.person.last_name}".strip() if admin_user.person else admin_user.username
        tracking_msg = (
            f"Jornada formativa reprogramada para el día {formatted_date} por {actor_name}. "
            f"Motivo: {reason.name}. Explicación técnica: {clean_justification}"
        )
        tracking = RequestTracking(
            request_id=req.id,
            user_id=admin_user.id,
            messages=tracking_msg
        )
        db.session.add(tracking)

        # 11. Actualizar timestamp de modificación en la solicitud
        req.updated_at = datetime.now(timezone.utc)

        # 12. Commit atómico
        db.session.commit()

        # 13. Despacho de notificaciones y correo institucional (bloque protegido)
        try:
            from app.notifications.services import NotificationService
            from app.notifications.enums import NotificationEvent
            from app.utils.email_utils import send_request_rescheduled_email

            training_name = req.training.name if req.training else "Tema Formativo"
            inst_name = req.institutional_staff.institution.institution_name if req.institutional_staff and req.institutional_staff.institution else "Plantel Educativo"

            context = {
                "institution_name": inst_name,
                "training_name": training_name,
                "new_date": formatted_date,
                "reason_name": reason.name,
                "justification": clean_justification
            }

            # Notificar en sistema a los afiliados del plantel
            if req.institutional_staff and req.institutional_staff.institution_id:
                NotificationService.notify_institution_affiliates(
                    institution_id=req.institutional_staff.institution_id,
                    event=NotificationEvent.REQUEST_RESCHEDULED,
                    context=context,
                    redirect_url=f"/requests/my-requests/{req.id}",
                    action_text="Ver Expediente",
                    db_session=db.session
                )

            # Notificar por correo asíncrono al solicitante
            if req.institutional_staff and req.institutional_staff.person and req.institutional_staff.person.email:
                applicant_p = req.institutional_staff.person
                applicant_name = f"{applicant_p.first_name} {applicant_p.last_name}".strip()
                send_request_rescheduled_email(
                    to_email=applicant_p.email,
                    full_name=applicant_name,
                    institution_name=inst_name,
                    request_code=req.request_code,
                    new_planned_date=formatted_date,
                    reason_name=reason.name,
                    justification=clean_justification
                )
        except Exception as notify_err:
            import logging
            logging.getLogger(__name__).error(f"Fallo no crítico al despachar comunicaciones de reprogramación (ID {req.id}): {notify_err}")

        return True, "Fecha de jornada formativa reprogramada exitosamente.", {
            "new_planned_for": formatted_date,
            "raw_new_date": parsed_date.isoformat(),
            "rescheduled_count": planning.rescheduled_count,
            "reason_name": reason.name
        }

    except Exception as e:
        db.session.rollback()
        import logging
        logging.getLogger(__name__).error(f"Error transaccional en reschedule_training_session (ID {request_id}): {e}")
        return False, "Ocurrió un error transaccional interno al reprogramar la jornada.", {}


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

# ---------------------------------------------------------------------------
# Agenda y Calendario Mensual de Formaciones (Sin Auditoría ni Notificaciones)
# ---------------------------------------------------------------------------

def get_monthly_calendar_events(user: User, year: int, month: int, state_id: int | None = None) -> dict:
    """
    Obtiene los eventos de solicitudes de formación agendados para el mes y año especificados.
    Aplica aislamiento territorial según el rol:
      - Admin Estadal: Restringido estrictamente a su estado de asignación.
      - Super Admin: Vista nacional con opción de filtrar por estado específico.
    Optimizado con joinedload para evitar consultas N+1.
    No incluye código de bitácora ni notificaciones.
    """
    import calendar
    from datetime import date

    # 1. Determinar roles del usuario
    user_roles = [assoc.role.name for assoc in user.roles_assoc] if user and user.roles_assoc else []
    is_super_admin = 'super_admin' in user_roles

    # 2. Control y aislamiento territorial
    effective_state_id = None
    if not is_super_admin:
        # Admin Estadal: Aislamiento territorial mandatorio
        admin_state_id = get_admin_state_id(user)
        if not admin_state_id:
            return {
                'success': False,
                'error': 'El usuario no posee una asignación territorial válida.',
                'year': year,
                'month': month,
                'user_role': 'state_admin',
                'events': [],
                'total_events': 0
            }
        effective_state_id = admin_state_id
    else:
        # Super Admin: Opcional si se solicita filtrar por un estado específico
        effective_state_id = int(state_id) if (state_id and str(state_id).isdigit()) else None

    # 3. Rango de fechas del mes
    _, num_days = calendar.monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, num_days)

    # 4. Construcción de consulta optimizada
    query = db.session.query(RequestPlanning).join(
        Request, RequestPlanning.requests_id == Request.id
    ).join(
        InstitutionalStaff, Request.institutional_staff_id == InstitutionalStaff.id
    ).join(
        Institution, InstitutionalStaff.institution_id == Institution.id
    ).join(
        Parish, Institution.parish_id == Parish.id
    ).join(
        Municipality, Parish.municipality_id == Municipality.id
    ).join(
        Status, Request.status_id == Status.id
    ).options(
        joinedload(RequestPlanning.request).joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
        joinedload(RequestPlanning.request).joinedload(Request.training),
        joinedload(RequestPlanning.request).joinedload(Request.attended_by).joinedload(User.person),
        joinedload(RequestPlanning.request).joinedload(Request.status)
    ).filter(
        RequestPlanning.planned_for.between(start_date, end_date),
        Request.historical == False,
        Status.status_code.notin_(['STAT-009', 'STAT-010'])
    )

    if effective_state_id:
        query = query.filter(Municipality.state_id == effective_state_id)

    # Ordenar cronológicamente
    plannings = query.order_by(RequestPlanning.planned_for.asc(), Request.id.asc()).all()

    # 5. Mapeo estructurado para el consumidor frontend
    events = []
    for plan in plannings:
        req = plan.request
        if not req:
            continue

        inst = req.institutional_staff.institution if (req.institutional_staff and req.institutional_staff.institution) else None
        inst_parish = inst.parish if inst else None
        inst_mun = inst_parish.municipality if inst_parish else None
        inst_state = inst_mun.state if inst_mun else None

        attended_person = req.attended_by.person if (req.attended_by and req.attended_by.person) else None
        operator_name = f"{attended_person.first_name} {attended_person.last_name}" if attended_person else "Sin Asignar"

        events.append({
            'id': plan.id,
            'request_id': req.id,
            'request_code': req.request_code,
            'date': plan.planned_for.strftime('%Y-%m-%d') if plan.planned_for else '',
            'status_code': req.status.status_code if req.status else 'STAT-005',
            'status_name': req.status.status_name if req.status else 'Planificada',
            'institution_name': inst.institution_name if inst else 'N/A',
            'topic_name': req.training.name if req.training else 'Sin Tema Asignado',
            'operator_name': operator_name,
            'operator_id': req.attended_by_id,
            'state_name': inst_state.name if inst_state else '',
            'state_id': inst_state.id if inst_state else None,
            'municipality_name': inst_mun.name if inst_mun else '',
            'detail_url': f"/requests/{req.id}/detail",
            'attended': plan.attended,
            'rescheduled_count': plan.rescheduled_count
        })

    return {
        'success': True,
        'year': year,
        'month': month,
        'user_role': 'super_admin' if is_super_admin else 'state_admin',
        'effective_state_id': effective_state_id,
        'events': events,
        'total_events': len(events)
    }

# ---------------------------------------------------------------------------
# Alerta de Cumplimiento Post-Fecha Pautada (Spam de Cierre)
# ---------------------------------------------------------------------------

def check_closure_spam_alert(req, user_id: int = None) -> dict:
    """
    Determina si el modal bloqueante de cierre debe activarse para una solicitud.

    Reglas de negocio:
    - La solicitud debe tener un administrador estadal asignado (attended_by_id).
    - Si se especifica user_id, debe coincidir con el administrador asignado.
    - La solicitud no debe ser histórica (historical == False).
    - La solicitud no debe estar en estado cerrado (STAT-007 / STAT-008 / STAT-009).
    - La solicitud tiene una fecha pautada (planned_for) en RequestPlanning.
    - La fecha actual ya superó esa fecha pautada (hoy > planned_for, es decir, día siguiente en adelante).
    - No existen evidencias cargadas (RequestEvidence vacío).
    """
    from datetime import date as date_cls

    CLOSED_STATUSES = {'STAT-007', 'STAT-008', 'STAT-009'}

    if getattr(req, 'historical', False):
        return {'should_trigger': False}

    if not req.status or req.status.status_code in CLOSED_STATUSES:
        return {'should_trigger': False}

    # 1. La solicitud debe tener un administrador asignado
    if not req.attended_by_id:
        return {'should_trigger': False}

    # Si se especifica un usuario, debe ser el administrador asignado a esta solicitud
    if user_id is not None and req.attended_by_id != user_id:
        return {'should_trigger': False}

    # 2. Buscar la planificación activa con fecha pautada
    active_planning = None
    if req.plannings:
        plans_with_date = [p for p in req.plannings if p.planned_for]
        if plans_with_date:
            active_planning = max(plans_with_date, key=lambda p: p.planned_for)

    if not active_planning:
        return {'should_trigger': False}

    today = date_cls.today()
    planned_date = active_planning.planned_for

    # El día de la formación (planned_date == today) se está cumpliendo la formación;
    # el spam se activa a partir del día siguiente (today > planned_date)
    if planned_date >= today:
        return {'should_trigger': False}

    # 3. Sin evidencias de cumplimiento registradas
    if req.evidences:
        return {'should_trigger': False}

    days_overdue = (today - planned_date).days
    rescheduled_count = active_planning.rescheduled_count or 0
    can_reschedule = (rescheduled_count < 1)

    return {
        'should_trigger': True,
        'days_overdue': days_overdue,
        'planned_date': planned_date.strftime('%d/%m/%Y'),
        'planned_date_iso': planned_date.isoformat(),
        'rescheduled_count': rescheduled_count,
        'can_reschedule': can_reschedule,
        'planning_id': active_planning.id,
    }


def get_blocking_closure_request_for_user(user_id: int):
    """
    Busca si el administrador estadal tiene alguna solicitud asignada que haya
    superado su fecha planificada de formación sin evidencias y sin cierre.
    Retorna la primera solicitud más vencida con toda su data cargada y la bandera closure_alert.
    """
    closed_statuses = ['STAT-007', 'STAT-008', 'STAT-009']

    candidate_requests = Request.query.join(
        Request.status
    ).filter(
        Request.attended_by_id == user_id,
        Request.historical == False,
        Status.status_code.notin_(closed_statuses),
        ~Request.evidences.any()
    ).options(
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.person),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality),
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.status),
        joinedload(Request.attended_by).joinedload(User.person),
        joinedload(Request.plannings),
        joinedload(Request.evidences)
    ).all()

    overdue_list = []
    for req in candidate_requests:
        alert = check_closure_spam_alert(req, user_id=user_id)
        if alert.get('should_trigger'):
            req.closure_alert = alert
            overdue_list.append(req)

    if not overdue_list:
        return None

    overdue_list.sort(key=lambda r: r.closure_alert.get('days_overdue', 0), reverse=True)
    return overdue_list[0]



def submit_closure_evidences(request_id: int, files, user_id: int) -> tuple:
    """
    Opción de cierre por evidencias: guarda los archivos de soporte digital y
    marca la solicitud como Completada (STAT-007).
    Solo puede ejecutarlo el administrador estadal asignado (attended_by_id).
    """
    import os
    import uuid
    from werkzeug.utils import secure_filename
    from app.models.request_evidence_model import RequestEvidence

    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
    MAX_FILE_SIZE = 5 * 1024 * 1024
    MAX_FILES = 3

    if not files:
        return False, "Debe adjuntar al menos un archivo de evidencia."

    if len(files) > MAX_FILES:
        return False, f"Solo se permiten hasta {MAX_FILES} archivos por cierre."

    req = Request.query.options(
        joinedload(Request.status),
        joinedload(Request.plannings)
    ).get(request_id)

    if not req:
        return False, "Solicitud no encontrada."

    if req.attended_by_id and req.attended_by_id != user_id:
        return False, "Solo el administrador asignado a esta solicitud puede cerrar este expediente."

    CLOSED_STATUSES = {'STAT-007', 'STAT-008', 'STAT-009'}
    if req.status and req.status.status_code in CLOSED_STATUSES:
        return False, "Esta solicitud ya se encuentra cerrada."

    validated = []
    for f in files:
        filename = secure_filename(f.filename or '')
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Formato no permitido: '{filename}'. Use PDF, JPG o PNG."
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        if size > MAX_FILE_SIZE:
            return False, f"El archivo '{filename}' supera el limite de 5 MB."
        validated.append((f, filename, ext, size))

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_dir = os.path.join(base_dir, 'static', 'uploads', 'evidences', str(request_id))
    os.makedirs(upload_dir, exist_ok=True)

    saved_paths = []
    try:
        for f, filename, ext, size in validated:
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            full_path = os.path.join(upload_dir, unique_name)
            f.save(full_path)
            relative_path = f"uploads/evidences/{request_id}/{unique_name}"
            saved_paths.append((unique_name, relative_path, ext, size))

        status_completed = Status.query.filter_by(status_code='STAT-007').first()
        if not status_completed:
            raise ValueError("Codigo de estado STAT-007 no encontrado en la base de datos.")

        now_utc = datetime.now(timezone.utc)

        for unique_name, relative_path, ext, size in saved_paths:
            evidence = RequestEvidence(
                request_id=request_id,
                file_name=unique_name,
                file_path=relative_path,
                format=ext.upper(),
                file_weight=size
            )
            db.session.add(evidence)

        req.status_id = status_completed.id
        req.finished_at = now_utc
        req.historical = True

        if req.plannings:
            plans_with_date = [p for p in req.plannings if p.planned_for]
            if plans_with_date:
                latest = max(plans_with_date, key=lambda p: p.planned_for)
                latest.attended = True
                latest.attended_at = now_utc

        db.session.commit()
        return True, "Solicitud cerrada exitosamente con las evidencias de cumplimiento."

    except Exception as e:
        db.session.rollback()
        for _, relative_path, _, _ in saved_paths:
            disk_path = os.path.join(base_dir, 'static', relative_path)
            if os.path.exists(disk_path):
                try:
                    os.remove(disk_path)
                except OSError:
                    pass
        import logging
        logging.getLogger(__name__).error(f"Error al cerrar solicitud {request_id} con evidencias: {e}")
        return False, "Error interno al procesar las evidencias. Intente nuevamente."


def submit_closure_reschedule(
    request_id: int,
    new_date_str: str,
    reason_id: int,
    justification_text: str,
    user_id: int
) -> tuple:
    """
    Opción de reprogramación del modal de cierre: registra una justificacion de tipo
    REPROGRAMACION_CIERRE y actualiza la fecha pautada a una nueva fecha futura.
    Solo se permite UNA reprogramación por solicitud (rescheduled_count < 1).
    No existe limite maximo de fecha, solo se prohiben fechas pasadas o iguales a hoy.
    """
    from datetime import date as date_cls
    from app.models.reason_model import Reason
    from app.models.request_justification_model import RequestJustification

    if not new_date_str:
        return False, "Debe indicar una nueva fecha para la reprogramacion."

    try:
        new_date = date_cls.fromisoformat(new_date_str)
    except ValueError:
        return False, "Formato de fecha invalido."

    if new_date <= date_cls.today():
        return False, "La nueva fecha debe ser posterior a hoy."

    if not justification_text or len(justification_text.strip()) < 20:
        return False, "La justificacion debe tener al menos 20 caracteres."

    if not reason_id:
        return False, "Debe seleccionar un motivo de reprogramacion."

    req = Request.query.options(
        joinedload(Request.status),
        joinedload(Request.plannings)
    ).get(request_id)

    if not req:
        return False, "Solicitud no encontrada."

    if req.attended_by_id and req.attended_by_id != user_id:
        return False, "Solo el administrador asignado a esta solicitud puede reprogramar este expediente."

    CLOSED_STATUSES = {'STAT-007', 'STAT-008', 'STAT-009'}
    if req.status and req.status.status_code in CLOSED_STATUSES:
        return False, "Esta solicitud ya se encuentra cerrada y no puede reprogramarse."

    reason = Reason.query.get(reason_id)
    if not reason:
        return False, "El motivo de reprogramacion seleccionado no es valido."

    active_planning = None
    if req.plannings:
        plans_with_date = [p for p in req.plannings if p.planned_for]
        if plans_with_date:
            active_planning = max(plans_with_date, key=lambda p: p.planned_for)

    if not active_planning:
        return False, "No se encontro una planificacion activa para esta solicitud."

    if (active_planning.rescheduled_count or 0) >= 1:
        return False, "Esta solicitud ya fue reprogramada anteriormente y no admite más reprogramaciones. Debe cargar los soportes de cumplimiento para cerrarla."

    try:
        justification = RequestJustification(
            request_id=request_id,
            reason_id=reason_id,
            justification_type='REPROGRAMACION_CIERRE',
            justification=justification_text.strip()
        )
        db.session.add(justification)

        active_planning.planned_for = new_date
        active_planning.rescheduled_count = (active_planning.rescheduled_count or 0) + 1

        db.session.commit()
        return True, f"Solicitud reprogramada al {new_date.strftime('%d/%m/%Y')} exitosamente."

    except Exception as e:
        db.session.rollback()
        import logging
        logging.getLogger(__name__).error(f"Error al reprogramar solicitud {request_id}: {e}")
        return False, "Error interno al guardar la reprogramacion. Intente nuevamente."


# ---------------------------------------------------------------------------
# Bloque Encuesta: Evaluación de Calidad Post-Cierre (US-51)
# ---------------------------------------------------------------------------

def submit_satisfaction_survey(request_id: int, form, user) -> tuple:
    """
    Persiste la evaluación de satisfacción post-cierre (US-51 / SR-F-019).

    Aplica bloqueo pesimista sobre la solicitud y re-verifica la unicidad
    para cubrir envíos concurrentes. El promedio se calcula exclusivamente
    en el servidor; el valor enviado por el cliente es ignorado.

    Retorna: (success: bool, message: str, http_status: int)
    """
    import html as html_lib
    import logging
    from app.models.rating_model import Rating

    logger = logging.getLogger(__name__)

    try:
        # 1. Bloqueo pesimista sobre la fila de la solicitud
        req = Request.query.with_for_update().get(request_id)
        if not req:
            return False, "Solicitud no encontrada.", 404

        # 2. Re-verificación de estado en backend (STAT-007 — Completado)
        if req.status.status_code != 'STAT-007':
            return False, "La solicitud no se encuentra en estado Completado.", 422

        # 3. Control de unicidad — anti-doble envío concurrente
        existing = Rating.query.filter_by(request_id=request_id).first()
        if existing:
            return False, "Esta solicitud ya fue evaluada previamente.", 409

        # 4. Sanitizar comentario para prevenir XSS
        raw_comment = (form.comment.data or '').strip()
        clean_comment = html_lib.escape(raw_comment) if raw_comment else None

        # 5. Calcular promedio aritmético redondeado (solo en backend, nunca del cliente)
        a = form.score_activity.data
        b = form.score_instructor.data
        c = form.score_admin_response.data
        score_avg = round((a + b + c) / 3, 2)

        # 6. Crear y persistir la entidad en sages.ratings
        rating = Rating(
            request_id=request_id,
            user_id=user.id,
            score_activity=a,
            score_instructor=b,
            score_admin_response=c,
            score=score_avg,
            comment=clean_comment
        )
        db.session.add(rating)
        db.session.commit()

        return True, "Evaluación registrada exitosamente.", 200

    except Exception as e:
        db.session.rollback()
        logger.error(
            f"Error al persistir encuesta de satisfacción (request_id={request_id}): {e}"
        )
        return False, "Error interno al procesar la evaluación. Intente nuevamente.", 500


def get_pending_survey_request(user_id: int):
    """
    Verifica si existe alguna solicitud completada (STAT-007) de la institución
    del solicitante que aún no posea registro de evaluación en sages.ratings.
    Retorna la primera solicitud pendiente encontrada, o None si no hay ninguna.
    """
    from app.models.rating_model import Rating

    user = User.query.get(user_id)
    if not user or not user.person or not user.person.institutional_staff:
        return None

    institution_id = user.person.institutional_staff[0].institution_id

    # Busca solicitudes en STAT-007 de esta institución que NO tengan rating
    pending_request = (
        Request.query.join(InstitutionalStaff)
        .join(Status, Request.status_id == Status.id)
        .outerjoin(Rating, Request.id == Rating.request_id)
        .filter(
            InstitutionalStaff.institution_id == institution_id,
            Status.status_code == 'STAT-007',
            Rating.id.is_(None)
        )
        .order_by(Request.id.asc())
        .first()
    )

    return pending_request

# ---------------------------------------------------------------------------
# Bloque Espacio de Trabajo Activo en Ejecución (Vista B.6 / US-46-actividad1)
# ---------------------------------------------------------------------------

def get_request_active_planning(req):
    """
    Retorna la planificación activa o más reciente asociada a la solicitud.
    """
    if not req or not req.plannings:
        return None
    plans_with_date = [p for p in req.plannings if p.planned_for is not None]
    if plans_with_date:
        return max(plans_with_date, key=lambda p: (p.planned_for, p.id))
    return req.plannings[-1] if req.plannings else None


def compute_workspace_evidence_metrics(evidences):
    """
    Calcula el balance y categorización de evidencias probatorias custodiadas
    """
    if not evidences:
        return {
            'total_evidences': 0,
            'pdf_count': 0,
            'photo_count': 0,
            'has_pdf_evidence': False,
            'has_photo_evidence': False,
            'can_complete': False
        }

    pdf_count = 0
    photo_count = 0

    for ev in evidences:
        fmt = (ev.format or '').strip().upper()
        name = (ev.file_name or '').strip().lower()
        if fmt == 'PDF' or name.endswith('.pdf'):
            pdf_count += 1
        elif fmt in ('JPG', 'JPEG', 'PNG') or any(name.endswith(ext) for ext in ('.jpg', '.jpeg', '.png')):
            photo_count += 1

    total = len(evidences)
    has_pdf = (pdf_count > 0)
    has_photo = (photo_count > 0)

    return {
        'total_evidences': total,
        'pdf_count': pdf_count,
        'photo_count': photo_count,
        'has_pdf_evidence': has_pdf,
        'has_photo_evidence': has_photo,
        'can_complete': (has_pdf and has_photo)
    }


def get_active_workspace_context(request_id: int, current_user=None) -> dict:
    """
    Recupera y estructura el contexto integral para el Espacio de Trabajo Activo
    """
    import logging
    from app.models.request_tracking_model import RequestTracking

    logger = logging.getLogger(__name__)

    try:
        # 1. Consulta optimizada con joinedload
        req = Request.query.options(
            joinedload(Request.status),
            joinedload(Request.training).joinedload(Training.training_module),
            joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution)
                .joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
            joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.person),
            joinedload(Request.attended_by).joinedload(User.person),
            joinedload(Request.plannings),
            joinedload(Request.justifications),
            joinedload(Request.evidences)
        ).get(request_id)

        if not req:
            return {
                'status': 'not_found',
                'message': 'Expediente de solicitud no encontrado en el sistema.'
            }

        # 2. Verificar si la solicitud ya está cerrada o archivada (Modo Histórico)
        status_code = req.status.status_code if req.status else ''
        if status_code in ('STAT-007', 'STAT-009') or req.historical:
            return {
                'status': 'redirect_history',
                'request_id': req.id,
                'message': 'Este expediente ya se encuentra culminado o archivado en modo de solo lectura.'
            }

        # 3. Si la solicitud está en STAT-003 (Nuevo sin atender), debe ser atendida en la consola
        if status_code == 'STAT-003':
            return {
                'status': 'redirect_inbox',
                'request_id': req.id,
                'message': 'La solicitud aún no ha sido aprobada ni asignada a un facilitador.'
            }

        active_planning = get_request_active_planning(req)
        today_utc = datetime.now(timezone.utc).date()

        # 4. Transición automática desatendida por llegada de la fecha pautada a STAT-006 (En Proceso)
        # Aplica si está en STAT-005 (Planificada) o STAT-004 con fecha agendada
        if active_planning and active_planning.planned_for and active_planning.planned_for <= today_utc:
            if status_code in ('STAT-004', 'STAT-005'):
                status_in_process = Status.query.filter_by(status_code='STAT-006').first()
                if status_in_process and req.status_id != status_in_process.id:
                    req.status_id = status_in_process.id
                    req.updated_at = datetime.now(timezone.utc)

                    actor_id = current_user.id if (current_user and current_user.is_authenticated) else (req.attended_by_id or 1)
                    auto_tracking = RequestTracking(
                        request_id=req.id,
                        user_id=actor_id,
                        messages="Llegada la fecha programada, la solicitud pasa formalmente a estado 'En Proceso' para ejecución presencial y carga de evidencias."
                    )
                    db.session.add(auto_tracking)
                    db.session.commit()

                    # Refrescar en memoria el estatus actual
                    req.status = status_in_process
                    status_code = 'STAT-006'

        # 5. Métricas de recaudos y evidencias digitales
        evidence_metrics = compute_workspace_evidence_metrics(req.evidences)

        # 5.1 Evaluación de Bloqueo ANS (has_delay_block) y Semáforo (idéntico a Ficha Técnica)
        vzla_tz = timezone(timedelta(hours=-4))
        now_local = datetime.now(vzla_tz)
        has_delay_block = False
        hours_diff = 0

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

        if has_delay_block and req.justifications:
            for just in req.justifications:
                if just.justification_type in ['RETRASO', 'REPROGRAMACION', 'RETRASO_ATENCION', 'RETRASO_EJECUCION']:
                    has_delay_block = False
                    break

        req.has_delay_block = has_delay_block

        base_text = req.status.status_name if req.status else 'En Proceso'
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

        # 5.2 Cálculo del Progreso Real de la Solicitud (Nuevo -> Pendiente -> Planificada -> En Proceso -> 100% con Evidencias)
        if evidence_metrics['can_complete'] or status_code == 'STAT-007':
            request_progress_pct = 100
        elif status_code == 'STAT-006':
            if evidence_metrics['has_photo_evidence'] or evidence_metrics['has_pdf_evidence']:
                request_progress_pct = 85
            else:
                request_progress_pct = 75
        elif status_code == 'STAT-005':
            request_progress_pct = 60
        elif status_code == 'STAT-004':
            request_progress_pct = 40
        elif status_code == 'STAT-003':
            request_progress_pct = 20
        else:
            request_progress_pct = 0

        evidence_metrics['request_progress_pct'] = request_progress_pct

        # 7. Estructuración de datos institucionales seguros
        inst = req.institutional_staff.institution if req.institutional_staff else None
        parish = inst.parish if inst else None
        municipality = parish.municipality if parish else None
        state = municipality.state if municipality else None
        contact_person = req.institutional_staff.person if req.institutional_staff else None

        contact_full_name = "No especificado"
        contact_phone = "No registrado"
        contact_email = "No registrado"
        if contact_person:
            contact_full_name = f"{contact_person.first_name or ''} {contact_person.last_name or ''}".strip() or "Contacto Institucional"
            contact_phone = contact_person.mobile or contact_person.phone or "No registrado"
            contact_email = contact_person.email or "No registrado"

        institution_data = {
            'name': inst.institution_name if inst else "Institución Educativa",
            'dea_code': (inst.plantel_code or inst.institution_code) if inst else "S/D",
            'state_name': state.name if state else "No asignado",
            'municipality_name': municipality.name if municipality else "No asignado",
            'parish_name': parish.name if parish else "No asignado",
            'address': inst.address if inst else "Dirección no registrada",
            'phone': inst.phone if (inst and inst.phone) else "No registrado",
            'contact_name': contact_full_name,
            'contact_phone': contact_phone,
            'contact_email': contact_email
        }

        # 8. Estructuración de datos pedagógicos UREE
        training = req.training
        module = training.training_module if training else None
        pedagogical_data = {
            'training_id': training.id if training else None,
            'training_name': training.name if training else "Tema Formativo UREE",
            'module_code': module.module_code if module else "MOD-001",
            'module_name': module.name if module else "UREE",
            'description': req.description or "Sin descripción pedagógica adicional."
        }

        # 9. Estructuración de datos del facilitador / titular
        facilitator_name = "Coordinación Regional UREE"
        facilitator_email = "uree@corpoelec.gob.ve"
        if req.attended_by:
            u = req.attended_by
            p = u.person if u else None
            if p:
                full_name = f"{p.first_name or ''} {p.last_name or ''}".strip()
                facilitator_name = full_name or getattr(u, 'user_name', 'Operador UREE')
                facilitator_email = p.email or facilitator_email
            else:
                facilitator_name = getattr(u, 'user_name', 'Administrador UREE')

        planned_date_str = active_planning.planned_for.strftime('%d/%m/%Y') if (active_planning and active_planning.planned_for) else "Por coordinar"

        facilitator_data = {
            'attended_by_id': req.attended_by_id,
            'facilitator_name': facilitator_name,
            'facilitator_email': facilitator_email,
            'planned_for_date': active_planning.planned_for if active_planning else None,
            'planned_for_str': planned_date_str,
            'rescheduled_count': active_planning.rescheduled_count or 0 if active_planning else 0,
            'original_planned_for': active_planning.original_planned_for if active_planning else None
        }

        from flask import url_for
        formatted_evidences = []
        for ev in (req.evidences or []):
            weight = ev.file_weight or 0
            w_str = f"{weight / 1024 / 1024:.2f} MB" if weight >= 1048576 else f"{weight / 1024:.1f} KB"
            created_dt = ev.created_at.astimezone(timezone(timedelta(hours=-4))) if ev.created_at else None
            try:
                v_url = url_for('requests.serve_request_evidence', evidence_id=ev.id)
            except RuntimeError:
                v_url = f"/requests/evidence/{ev.id}/view"
            formatted_evidences.append({
                'id': ev.id,
                'file_name': ev.file_name,
                'file_path': ev.file_path,
                'format': (ev.format or '').upper(),
                'file_weight': weight,
                'file_weight_str': w_str,
                'created_at': ev.created_at,
                'created_at_str': created_dt.strftime('%d/%m/%Y %I:%M %p') if created_dt else '',
                'view_url': v_url,
                'download_url': f"{v_url}?download=1"
            })

        return {
            'status': 'success',
            'request': req,
            'active_planning': active_planning,
            'institution_data': institution_data,
            'pedagogical_data': pedagogical_data,
            'facilitator_data': facilitator_data,
            'evidence_metrics': evidence_metrics,
            'evidences': formatted_evidences,
            'tracking_steps': get_request_timeline(request_id)
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al generar contexto del espacio de trabajo activo (request_id={request_id}): {e}", exc_info=True)
        return {
            'status': 'error',
            'message': 'Error interno al procesar el expediente en el espacio de trabajo.'
        }


# ---------------------------------------------------------------------------
# Bloque Auditoría Forense y Trazabilidad Nacional (US-45-actividad2 / Vista A.3)
# ---------------------------------------------------------------------------

def get_forensic_audit_detail(request_id: int) -> dict:
    """
    Obtiene la radiografía técnica y forense inalterable de una solicitud (US-45).
    Aplica carga ansiosa profunda (joinedload) sobre todas las entidades satélites
    para garantizar máxima eficiencia y cero N+1 queries.
    
    Regla de Presentación Institucional:
    - Cero exposición de códigos internos de base de datos (STAT-xxx, IDs primarios o foráneos).
    - Despliega denominaciones institucionales legibles y amigables.
    """
    from flask import current_app, url_for
    from app.models.training_module_model import TrainingModule
    from app.models.person_model import Person
    from app.models.request_evidence_model import RequestEvidence
    from app.models.request_tracking_model import RequestTracking
    from app.utils.qr_generator import generate_verification_token
    import os

    req = db.session.query(Request).options(
        joinedload(Request.status),
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.person),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.institution_type),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.institution_scope),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.institution_dependency),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.position),
        joinedload(Request.attended_by).joinedload(User.person),
        joinedload(Request.plannings),
        joinedload(Request.justifications).joinedload(RequestJustification.reason),
        joinedload(Request.evidences),
        joinedload(Request.tracking_steps).joinedload(RequestTracking.user).joinedload(User.person),
        joinedload(Request.tracking_steps).joinedload(RequestTracking.user).joinedload(User.roles_assoc)
    ).filter(Request.id == request_id).first_or_404()

    vzla_tz = timezone(timedelta(hours=-4))
    now_vzla = datetime.now(vzla_tz)
    created_vzla = req.created_at.astimezone(vzla_tz) if req.created_at else now_vzla
    updated_vzla = req.updated_at.astimezone(vzla_tz) if req.updated_at else now_vzla

    # 1. Tiempos y Métricas de ANS
    status_code = req.status.status_code if req.status else ''
    status_name = req.status.status_name if req.status else 'En Proceso'

    hours_diff = (now_vzla - created_vzla).total_seconds() / 3600
    days_elapsed = int(hours_diff // 24)
    hours_remainder = int(hours_diff % 24)

    is_exceeded = False
    sla_badge_class = 'badge-sla-normal'
    sla_text = 'Dentro de Parámetros Normativos'
    sla_level = 'NORMAL'

    # Verificación de justificaciones previas
    has_justification = False
    latest_justification = None
    if req.justifications:
        for just in req.justifications:
            if just.justification_type in ['RETRASO', 'REPROGRAMACION', 'RETRASO_ATENCION', 'RETRASO_EJECUCION']:
                has_justification = True
                latest_justification = just
                break

    if status_code == 'STAT-003':
        # Atención inicial: Máximo 72h (3 días)
        if hours_diff > 72:
            is_exceeded = True
            sla_level = 'CRITICO'
            sla_badge_class = 'badge-sla-critical'
            sla_text = f'Mora de Atención ({days_elapsed}d {hours_remainder}h sin asignar)'
        elif hours_diff > 48:
            sla_level = 'ALERTA'
            sla_badge_class = 'badge-sla-warning'
            sla_text = 'Atención Próxima a Vencer (>48h)'
    elif status_code in ['STAT-004', 'STAT-005', 'STAT-006']:
        # Ejecución presencial: 240h (10 días)
        execution_hours = (now_vzla - updated_vzla).total_seconds() / 3600
        if execution_hours > 240:
            is_exceeded = True
            sla_level = 'CRITICO'
            sla_badge_class = 'badge-sla-critical'
            exec_days = int(execution_hours // 24)
            sla_text = f'Mora de Ejecución ({exec_days} días en proceso)'
        elif execution_hours > 168:
            sla_level = 'ALERTA'
            sla_badge_class = 'badge-sla-warning'
            sla_text = 'Alerta de Tiempo de Ejecución (>7 días)'
    elif status_code == 'STAT-007':
        sla_level = 'COMPLETADO'
        sla_badge_class = 'badge-sla-success'
        sla_text = 'Expediente Concluido Satisfactoriamente'
    elif status_code in ['STAT-008', 'STAT-009']:
        sla_level = 'ARCHIVADO'
        sla_badge_class = 'badge-sla-archived'
        sla_text = status_name

    can_demand_justification = (is_exceeded and not has_justification and status_code not in ['STAT-007', 'STAT-008', 'STAT-009'])

    # 2. Sello Criptográfico SHA-256
    token = generate_verification_token(req.request_code, req.id)
    token_display = token[:8].upper()
    verification_url = f"/requests/verify/{token}"

    # 3. Línea de Tiempo Forense (Cronología Inalterable)
    sorted_steps = sorted(req.tracking_steps, key=lambda t: t.created_at or datetime.min)
    timeline_entries = []

    ROLE_LABELS = {
        'super_admin': 'Super Administrador Nacional',
        'state_admin': 'Coordinación Estadal UREE',
        'applicant': 'Representante del Plantel'
    }

    for step in sorted_steps:
        step_vzla = step.created_at.astimezone(vzla_tz) if step.created_at else now_vzla
        step_utc = step.created_at.astimezone(timezone.utc) if step.created_at else now_vzla

        # Detección de autor
        author_name = "Sistema Automatizado SAGES"
        author_role = "Plataforma Institucional"
        author_initials = "SG"
        is_system = True

        if step.user:
            u = step.user
            p = u.person if u else None
            if p:
                first = (p.first_name or '').strip()
                last = (p.last_name or '').strip()
                author_name = f"{first} {last}".strip() or u.user_name
                author_initials = f"{first[:1]}{last[:1]}".upper() if (first and last) else u.user_name[:2].upper()
            else:
                author_name = u.user_name
                author_initials = u.user_name[:2].upper()

            role_code = u.roles_assoc[0].role.name if (u.roles_assoc and u.roles_assoc[0].role) else 'system'
            author_role = ROLE_LABELS.get(role_code, 'Funcionario Corporativo')
            is_system = (role_code not in ROLE_LABELS)

        # Categorización semántica del hito para iconografía y estilo
        msg_upper = (step.messages or '').upper()
        if any(w in msg_upper for w in ['RADICADA', 'CREADA', 'REGISTRADA', 'SOLICITUD REGISTRADA']):
            node_type = 'creation'
            node_label = 'Radicación Inicial'
            node_color = 'cyan'
        elif any(w in msg_upper for w in ['ASIGNADA', 'ATENDER', 'ASIGNACIÓN']):
            node_type = 'assignment'
            node_label = 'Asignación Técnica'
            node_color = 'blue'
        elif any(w in msg_upper for w in ['PLANIFICADA', 'FECHA AGENDADA', 'CRONOGRAMA']):
            node_type = 'planning'
            node_label = 'Planificación Acordada'
            node_color = 'teal'
        elif any(w in msg_upper for w in ['REPROGRAMACIÓN', 'REPROGRAMADA', 'PRÓRROGA']):
            node_type = 'reschedule'
            node_label = 'Reprogramación'
            node_color = 'amber'
        elif any(w in msg_upper for w in ['JUSTIFICACIÓN', 'DESCARGO', 'MORA']):
            node_type = 'justification'
            node_label = 'Descargo Técnico'
            node_color = 'purple'
        elif any(w in msg_upper for w in ['EXIGENCIA', 'INTIMACIÓN', 'COERCITIVO', 'REQUERIMIENTO']):
            node_type = 'demand'
            node_label = 'Fiscalización Superior'
            node_color = 'red'
        elif any(w in msg_upper for w in ['COMPLETADA', 'CIERRE', 'EJECUTADA', 'CONCLUIDA']):
            node_type = 'completion'
            node_label = 'Cierre Operativo'
            node_color = 'green'
        elif any(w in msg_upper for w in ['CANCELADA', 'DESISTIMIENTO', 'RECHAZADA']):
            node_type = 'cancellation'
            node_label = 'Cancelación'
            node_color = 'gray'
        else:
            node_type = 'general'
            node_label = 'Nota de Bitácora'
            node_color = 'slate'

        timeline_entries.append({
            'id': step.id,
            'message': step.messages,
            'created_at_vzla': step_vzla.strftime('%d/%m/%Y %I:%M:%S %p'),
            'created_at_utc': step_utc.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'author_name': author_name,
            'author_role': author_role,
            'author_initials': author_initials,
            'is_system': is_system,
            'node_type': node_type,
            'node_label': node_label,
            'node_color': node_color
        })

    # 4. Galería de Evidencias Custodiadas
    formatted_evidences = []
    for ev_idx, ev in enumerate(req.evidences or [], 1):
        ev_vzla = ev.created_at.astimezone(vzla_tz) if ev.created_at else now_vzla
        fmt = (ev.format or 'PDF').upper()
        if fmt == 'JPEG':
            fmt = 'JPG'

        weight = ev.file_weight or 0
        if weight >= 1024 * 1024:
            weight_str = f"{weight / (1024 * 1024):.2f} MB"
        else:
            weight_str = f"{max(1, round(weight / 1024))} KB"

        # Limpieza de nombre de archivo institucional (cero códigos técnicos o hashes de BD)
        import re as _re, os as _os
        raw_name = (ev.file_name or '').strip()
        base, ext_part = _os.path.splitext(raw_name)
        if not ext_part and fmt:
            ext_part = '.' + fmt.lower()

        # Caso 1: Si viene con prefijo hash o UUID seguido de guion bajo
        parts = base.split('_', 1)
        if len(parts) == 2 and _re.match(r'^[0-9a-fA-F\-]{8,}$', parts[0]):
            clean_name = parts[1] + ext_part
        else:
            clean_name = raw_name

        # Caso 2: Si el nombre base es un hash, código puramente numérico o término genérico
        clean_base, clean_ext = _os.path.splitext(clean_name)
        if (
            not clean_name
            or clean_base.isdigit()
            or _re.match(r'^[0-9a-fA-F\-]{8,}$', clean_base)
            or clean_base.lower() in ('file', 'evidence', 'soporte', 'upload', 'blob', 'image', 'imagen', 'documento', 'archivo')
        ):
            ext_label = clean_ext if clean_ext else ext_part
            clean_name = f"Soporte Documental N°{ev_idx}{ext_label}"

        display_filename = clean_name

        formatted_evidences.append({
            'id': ev.id,
            'file_name': display_filename,
            'format': fmt,
            'is_pdf': fmt == 'PDF',
            'is_image': fmt in ['JPG', 'JPEG', 'PNG'],
            'file_weight_str': weight_str,
            'created_at_str': ev_vzla.strftime('%d/%m/%Y %I:%M %p'),
            'view_url': url_for('requests.serve_request_evidence', evidence_id=ev.id),
            'download_url': url_for('requests.serve_request_evidence', evidence_id=ev.id) + '?download=1'
        })

    # 5. Compromiso Operativo y Planificación
    active_plan = None
    if req.plannings:
        plans_with_date = [p for p in req.plannings if p.planned_for]
        active_plan = max(plans_with_date, key=lambda p: p.planned_for) if plans_with_date else req.plannings[-1]

    # Facilitador asignado
    facilitator_name = "Sin Asignar (Bandeja Abierta)"
    facilitator_email = "No asignado"
    facilitator_phone = "No disponible"
    if req.attended_by:
        u = req.attended_by
        p = u.person if u else None
        if p:
            facilitator_name = f"{p.first_name or ''} {p.last_name or ''}".strip()
            facilitator_email = p.email or "Sin correo registrado"
            facilitator_phone = p.mobile or p.phone or "Sin teléfono registrado"
        else:
            facilitator_name = u.user_name

    # 6. Datos Institucionales y de Jurisdicción (Sin códigos técnicos de BD)
    inst = req.institutional_staff.institution if (req.institutional_staff and req.institutional_staff.institution) else None
    staff_person = req.institutional_staff.person if (req.institutional_staff and req.institutional_staff.person) else None
    position_obj = req.institutional_staff.position if req.institutional_staff else None

    parish_name = inst.parish.name if (inst and inst.parish) else "No especificada"
    muni_name = inst.parish.municipality.name if (inst and inst.parish and inst.parish.municipality) else "No especificado"
    state_name = inst.parish.municipality.state.name if (inst and inst.parish and inst.parish.municipality and inst.parish.municipality.state) else "Nacional"

    inst_data = {
        'name': inst.institution_name if inst else "Institución no disponible",
        'plantel_code': inst.plantel_code if inst else "N/A",  # Código DEA oficial
        'institution_code': inst.institution_code if inst else "N/A",
        'type': inst.institution_type.name if (inst and inst.institution_type) else "Plantel Educativo",
        'scope': inst.institution_scope.name if (inst and inst.institution_scope) else "Urbano / Regional",
        'dependency': inst.institution_dependency.name if (inst and inst.institution_dependency) else "Pública Oficial",
        'address': inst.address if inst else "Dirección no consignada",
        'phone': inst.phone if inst else "No consignado",
        'state': state_name,
        'municipality': muni_name,
        'parish': parish_name
    }

    applicant_data = {
        'full_name': f"{staff_person.first_name} {staff_person.last_name}".strip() if staff_person else "Solicitante Institucional",
        'id_card': f"{staff_person.identification_type}-{staff_person.identification_number}" if staff_person else "N/A",
        'email': staff_person.email if staff_person else "No consignado",
        'mobile': staff_person.mobile or staff_person.phone or "No consignado",
        'position': position_obj.name if position_obj else "Representante Institucional"
    }

    return {
        'request': req,
        'request_code': req.request_code,
        'status_name': status_name,  # Denominación institucional amigable
        'description': req.description,
        'created_at_vzla': created_vzla.strftime('%d/%m/%Y %I:%M:%S %p'),
        'created_at_utc': req.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if req.created_at else '',
        'updated_at_vzla': updated_vzla.strftime('%d/%m/%Y %I:%M:%S %p'),
        'finished_at_vzla': req.finished_at.astimezone(vzla_tz).strftime('%d/%m/%Y %I:%M:%S %p') if req.finished_at else None,
        'days_elapsed': days_elapsed,
        'hours_remainder': hours_remainder,
        'token_display': token_display,
        'verification_url': verification_url,
        'sla': {
            'level': sla_level,
            'badge_class': sla_badge_class,
            'text': sla_text,
            'is_exceeded': is_exceeded,
            'has_justification': has_justification,
            'can_demand_justification': can_demand_justification,
            'latest_justification': latest_justification
        },
        'timeline': timeline_entries,
        'evidences': formatted_evidences,
        'institution': inst_data,
        'applicant': applicant_data,
        'operational': {
            'facilitator_name': facilitator_name,
            'facilitator_email': facilitator_email,
            'facilitator_phone': facilitator_phone,
            'is_assigned': req.attended_by_id is not None,
            'planned_for': active_plan.planned_for.strftime('%d/%m/%Y') if (active_plan and active_plan.planned_for) else "Por coordinar",
            'original_planned_for': active_plan.original_planned_for.strftime('%d/%m/%Y') if (active_plan and active_plan.original_planned_for) else None,
            'rescheduled_count': active_plan.rescheduled_count if active_plan else 0,
            'execution_deadline': active_plan.execution_deadline.astimezone(vzla_tz).strftime('%d/%m/%Y') if (active_plan and active_plan.execution_deadline) else None
        },
        'training': {
            'topic_name': req.training.name if req.training else "Módulo General",
            'module_name': req.training.training_module.name if (req.training and req.training.training_module) else "Programa Formativo UREE",
            'module_code': req.training.training_module.module_code if (req.training and req.training.training_module) else ""
        }
    }


def get_safe_evidence_path(evidence_id: int, user) -> tuple:
    """
    Resuelve y valida de manera segura la ruta física en disco de una evidencia resguardada.
    Aplica controles RBAC, multi-tenant estadal y blindaje estricto contra Path Traversal.
    
    Retorna: ((safe_dir, safe_file, mimetype, original_name), error_msg, status_code)
    """
    import os
    from flask import current_app
    from app.models.request_evidence_model import RequestEvidence

    evidence = db.session.query(RequestEvidence).options(
        joinedload(RequestEvidence.request).joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality)
    ).filter(RequestEvidence.id == evidence_id).first()

    if not evidence:
        return None, "El registro de evidencia no fue encontrado.", 404

    # 1. Control de Acceso RBAC
    user_roles = [assoc.role.name for assoc in user.roles_assoc] if (user and user.roles_assoc) else []
    is_super = 'super_admin' in user_roles
    is_state = 'state_admin' in user_roles

    if not (is_super or is_state):
        current_app.logger.warning(f"[SECURITY] Usuario {getattr(user, 'id', None)} sin rol auditor intentó acceder a evidencia {evidence_id}")
        return None, "No posee privilegios de fiscalización documental.", 403

    if is_state and not is_super:
        user_state_id = None
        if user and user.person and user.person.company_staff:
            try:
                user_state_id = user.person.company_staff[0].place.parish.municipality.state_id
            except (IndexError, AttributeError):
                user_state_id = None

        req_state_id = None
        try:
            req_state_id = evidence.request.institutional_staff.institution.parish.municipality.state_id
        except (AttributeError, IndexError):
            req_state_id = None

        if user_state_id is None or req_state_id != user_state_id:
            current_app.logger.warning(f"[SECURITY] state_admin {user.id} intentó acceder a evidencia ajena a su estado.")
            return None, "No tiene autorización para expedientes fuera de su jurisdicción estadal.", 403

    # 2. Blindaje Anti-Path Traversal
    raw_path = (evidence.file_path or '').strip().lstrip('/\\')
    file_name = evidence.file_name or os.path.basename(raw_path)

    # Detección temprana de secuencias maliciosas
    if any(seq in raw_path for seq in ['..', '%2e%2e', '\0', '\\..', '/..']):
        current_app.logger.error(f"[SECURITY] Detección de Path Traversal en evidencia {evidence_id}: {raw_path}")
        return None, "Secuencia de ruta inválida detectada.", 403

    # Directorios base autorizados
    base_upload_folder = current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, '..', 'uploads'))
    static_upload_folder = os.path.join(current_app.root_path, 'static')

    allowed_roots = [
        os.path.realpath(os.path.abspath(base_upload_folder)),
        os.path.realpath(os.path.abspath(static_upload_folder)),
        os.path.realpath(os.path.abspath(os.path.join(current_app.root_path, 'static', 'uploads')))
    ]

    # Resolver candidatos en disco
    candidate_paths = [
        os.path.abspath(os.path.join(static_upload_folder, raw_path)),
        os.path.abspath(os.path.join(current_app.root_path, 'static', 'uploads', 'evidences', str(evidence.request_id), file_name)),
        os.path.abspath(os.path.join(base_upload_folder, raw_path)),
        os.path.abspath(os.path.join(base_upload_folder, 'evidences', str(evidence.request_id), file_name)),
        os.path.abspath(os.path.join(current_app.root_path, 'static', 'uploads', file_name))
    ]

    resolved_path = None
    for cand in candidate_paths:
        real_cand = os.path.realpath(cand)
        is_safe = False
        for root in allowed_roots:
            if real_cand.startswith(root) and len(real_cand) > len(root):
                is_safe = True
                break

        if is_safe and os.path.isfile(real_cand):
            resolved_path = real_cand
            break

    if not resolved_path:
        current_app.logger.warning(f"Evidencia {evidence_id} física no encontrada en rutas candidatas para: {raw_path}")
        return None, "El archivo probatorio no se encuentra disponible físicamente en el servidor.", 404

    # Determinar MIME Type seguro
    fmt = (evidence.format or os.path.splitext(resolved_path)[1].replace('.', '')).lower()
    MIME_TYPES = {
        'pdf': 'application/pdf',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png'
    }
    mimetype = MIME_TYPES.get(fmt, 'application/octet-stream')

    safe_dir = os.path.dirname(resolved_path)
    safe_file = os.path.basename(resolved_path)

    return (safe_dir, safe_file, mimetype, file_name), None, 200
 
 # ---------------------------------------------------------------------------
# Bloque Bitácora de Seguimiento Transversal y Trazabilidad (US-45)
# ---------------------------------------------------------------------------

def get_request_timeline(request_id: int) -> list:
    """
    Recupera y formatea la cronología completa de la solicitud (sages.request_trackings),
    ordenada de forma ascendente (created_at ASC).
    Diferencia hitos automáticos del sistema de notas humanas con su autor y cargo institucional.
    """
    from app.models.request_tracking_model import RequestTracking
    from app.models.role_user_model import RoleUser
    from app.models.role_model import Role

    trackings = RequestTracking.query.options(
        joinedload(RequestTracking.user).joinedload(User.person),
        joinedload(RequestTracking.user).joinedload(User.roles_assoc).joinedload(RoleUser.role)
    ).filter(
        RequestTracking.request_id == request_id
    ).order_by(
        RequestTracking.created_at.asc(),
        RequestTracking.id.asc()
    ).all()

    vzla_tz = timezone(timedelta(hours=-4))
    formatted_steps = []

    for step in trackings:
        clean_msg = (step.messages or '').strip()
        is_system = False
        if clean_msg.startswith("Sistema:") or clean_msg.startswith("Llegada la fecha programada"):
            is_system = True

        author_name = "Sistema SAGES"
        author_role = "Automático"

        if not is_system and step.user:
            u = step.user
            p = u.person if u else None
            if p:
                full_name = f"{p.first_name or ''} {p.last_name or ''}".strip()
                author_name = full_name or getattr(u, 'user_name', 'Usuario SAGES')
            else:
                author_name = getattr(u, 'user_name', 'Usuario SAGES')

            # Determinar cargo o rol
            user_roles = [ra.role.name for ra in u.roles_assoc if ra.role] if u.roles_assoc else []
            if 'super_admin' in user_roles:
                author_role = "Gerencia UREE (Super Admin)"
            elif 'state_admin' in user_roles:
                author_role = "Facilitador / Administrador UREE"
            elif 'applicant' in user_roles:
                author_role = "Directivo / Solicitante del Plantel"
            else:
                author_role = "Operador SAGES"

        if step.created_at:
            dt_local = step.created_at.astimezone(vzla_tz) if step.created_at.tzinfo else step.created_at
            created_str = dt_local.strftime('%d/%m/%Y %I:%M %p')
        else:
            created_str = "Fecha no registrada"

        formatted_steps.append({
            'id': step.id,
            'user_id': step.user_id,
            'author': author_name,
            'author_role': author_role,
            'message': clean_msg,
            'created_at': step.created_at.isoformat() if step.created_at else None,
            'created_at_str': created_str,
            'is_system': is_system
        })

    return formatted_steps


def add_tracking_note(request_id: int, note_text: str, user: User) -> tuple:
    """
    Sanitiza, valida y persiste una observación o nota humana en sages.request_trackings.
    Retorna (success: bool, message: str, note_data: dict).
    """
    import logging
    from markupsafe import escape
    from app.models.request_tracking_model import RequestTracking

    logger = logging.getLogger(__name__)

    try:
        text_clean = (note_text or '').strip()
        if not text_clean:
            return False, "El contenido de la observación no puede estar vacío.", {}

        if len(text_clean) > 1000:
            return False, "La observación no debe exceder los 1000 caracteres.", {}

        req = Request.query.get(request_id)
        if not req:
            return False, "Expediente de solicitud no encontrado.", {}

        if req.historical or (req.status and req.status.status_code == 'STAT-009'):
            return False, "No se pueden asentar notas en un expediente archivado o cancelado.", {}

        # Sanitización estricta contra inyecciones XSS
        sanitized_message = str(escape(text_clean))

        now_utc = datetime.now(timezone.utc)
        new_step = RequestTracking(
            request_id=request_id,
            user_id=user.id,
            messages=sanitized_message,
            created_at=now_utc
        )
        db.session.add(new_step)
        db.session.commit()

        # Determinar rol y nombre
        vzla_tz = timezone(timedelta(hours=-4))
        dt_local = now_utc.astimezone(vzla_tz)
        created_str = dt_local.strftime('%d/%m/%Y %I:%M %p')

        p = user.person if user else None
        author_name = f"{p.first_name or ''} {p.last_name or ''}".strip() if p else getattr(user, 'user_name', 'Usuario SAGES')

        user_roles = [ra.role.name for ra in user.roles_assoc if ra.role] if (user and user.roles_assoc) else []
        if 'super_admin' in user_roles:
            author_role = "Gerencia UREE (Super Admin)"
        elif 'state_admin' in user_roles:
            author_role = "Facilitador / Administrador UREE"
        elif 'applicant' in user_roles:
            author_role = "Directivo / Solicitante del Plantel"
        else:
            author_role = "Operador SAGES"

        note_data = {
            'id': new_step.id,
            'user_id': user.id,
            'author': author_name,
            'author_role': author_role,
            'message': sanitized_message,
            'created_at': now_utc.isoformat(),
            'created_at_str': created_str,
            'is_system': False
        }

        return True, "Nota asentada exitosamente en la bitácora.", note_data

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al registrar nota en tracking (request_id={request_id}): {e}", exc_info=True)
        return False, "Error interno al asentar la observación.", {}


def log_system_milestone(request_id: int, message_text: str, user_id: int = None) -> bool:
    """
    Estampa un hito formal del sistema en sages.request_trackings.
    Garantiza que user_id no sea nulo respetando la integridad referencial.
    """
    import logging
    from flask_login import current_user
    from app.models.request_tracking_model import RequestTracking

    logger = logging.getLogger(__name__)

    try:
        clean_msg = (message_text or '').strip()
        if not clean_msg:
            return False

        if not clean_msg.startswith("Sistema:"):
            clean_msg = f"Sistema: {clean_msg}"

        resolved_user_id = user_id
        if not resolved_user_id:
            if current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'id', None):
                resolved_user_id = current_user.id
            else:
                req = Request.query.get(request_id)
                resolved_user_id = (req.attended_by_id if (req and req.attended_by_id) else 1)

        milestone = RequestTracking(
            request_id=request_id,
            user_id=resolved_user_id,
            messages=clean_msg,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(milestone)
        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al registrar hito del sistema (request_id={request_id}): {e}", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Portal Público de Validación de Autenticidad QR (US-52)
# ---------------------------------------------------------------------------

def validate_document_qr_token(token: str) -> dict | None:
    """
    US-52: Portal Público de Verificación de Autenticidad mediante Código QR.
    Consulta relacional ultrarrápida filtrando por verification_token indexado (uq_requests_verification_token).
    Aplica carga ansiosa profunda (joinedload) en un solo viaje a la base de datos (< 20 ms).
    Retorna un diccionario estructurado y sanitizado con datos públicos institucionales,
    garantizando ofuscación estricta de datos sensibles (cero cédulas, teléfonos o correos privados).
    Si el token no existe o no coincide, retorna None.
    """
    if not token or len(token) != 64:
        return None

    from app.models.training_module_model import TrainingModule
    from app.models.person_model import Person

    req = db.session.query(Request).options(
        joinedload(Request.status),
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
        joinedload(Request.attended_by).joinedload(User.person),
        joinedload(Request.plannings)
    ).filter(Request.verification_token == token).first()

    if not req:
        return None

    # Zona horaria de Venezuela (UTC-4)
    vzla_tz = timezone(timedelta(hours=-4))

    # 1. Datos de la Institución Educativa
    institution = None
    if req.institutional_staff and req.institutional_staff.institution:
        institution = req.institutional_staff.institution

    inst_name = institution.institution_name if institution else "Institución Educativa No Especificada"
    plantel_code = getattr(institution, 'plantel_code', None) or "No asignado"

    parish_name = "No especificada"
    muni_name = "No especificado"
    state_name = "Nacional"
    if institution and institution.parish:
        parish_name = institution.parish.name or "No especificada"
        if institution.parish.municipality:
            muni_name = institution.parish.municipality.name or "No especificado"
            if institution.parish.municipality.state:
                state_name = institution.parish.municipality.state.name or "Nacional"

    # 2. Datos Formativos
    training_name = req.training.name if req.training else "Formación en Uso Eficiente de la Energía"
    module_name = req.training.training_module.name if (req.training and req.training.training_module) else "Programa Rector UREE"

    # 3. Estatus Operativo Institucional
    status_code = req.status.status_code if req.status else "STAT-003"
    status_name = req.status.status_name if req.status else "Nuevo"

    status_badges = {
        'STAT-003': ('badge-nuevo', 'Nuevo'),
        'STAT-004': ('badge-pendiente', 'Pendiente'),
        'STAT-005': ('badge-planificada', 'Planificada'),
        'STAT-006': ('badge-proceso', 'En Proceso'),
        'STAT-007': ('badge-completado', 'Completado'),
        'STAT-008': ('badge-rechazado', 'Rechazado'),
        'STAT-009': ('badge-cancelado', 'Cancelado')
    }
    badge_class, _ = status_badges.get(status_code, ('badge-info', status_name))

    # 4. Fechas Oficiales Formateadas
    MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", 
                 "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

    def _fmt_date(dt):
        if not dt:
            return None
        dt_local = dt.astimezone(vzla_tz) if dt.tzinfo else dt
        return f"{dt_local.day} de {MONTHS_ES[dt_local.month - 1]} del {dt_local.year}"

    official_date_label = "Fecha Oficial de Radicación"
    if req.finished_at and status_code == 'STAT-007':
        official_date_str = _fmt_date(req.finished_at)
        official_date_label = "Fecha Oficial de Culminación"
    elif req.created_at:
        official_date_str = _fmt_date(req.created_at)
        official_date_label = "Fecha Oficial de Radicación"
    else:
        official_date_str = "Fecha no registrada"

    # 5. Facilitador o Coordinación Responsable UREE
    facilitator_name = None
    if req.attended_by and req.attended_by.person:
        p = req.attended_by.person
        facilitator_name = f"{p.first_name or ''} {p.last_name or ''}".strip()
    elif req.attended_by:
        facilitator_name = req.attended_by.user_name

    # Formateo estético del token para la credencial (bloques de 4 caracteres)
    token_upper = token[:16].upper()
    formatted_token = f"{token_upper[:4]}-{token_upper[4:8]}-{token_upper[8:12]}-{token_upper[12:16]}"

    return {
        'request_code': req.request_code,
        'institution_name': inst_name,
        'plantel_code': plantel_code,
        'location': f"{state_name} / {muni_name} / {parish_name}",
        'state_name': state_name,
        'municipality_name': muni_name,
        'parish_name': parish_name,
        'training_name': training_name,
        'module_name': module_name,
        'status_code': status_code,
        'status_name': status_name,
        'status_badge_class': badge_class,
        'official_date': official_date_str,
        'official_date_label': official_date_label,
        'facilitator_name': facilitator_name or "Coordinación Estadal UREE",
        'responsible_office': f"Gerencia General de UREE — Coordinación {state_name}",
        'token_display': formatted_token,
        'is_completed': (status_code == 'STAT-007')
    }
    
# ---------------------------------------------------------------------------
# Bloque Evidencias Digitales de Ejecución
# ---------------------------------------------------------------------------

def attach_request_evidence(request_id: int, file_obj, user) -> tuple:
    """
    Adjunta y custodia de manera segura un archivo de soporte (fotografía o acta PDF)
    para una solicitud que se encuentra en ejecución presencial (STAT-006).

    Aplica:
      - Validación de existencia y estado FSM (estrictamente STAT-006).
      - Control de titularidad y territorialidad (facilitador asignado o super_admin).
      - Validación de Magic Bytes y límite de 5 MB mediante file_handler.py.
      - Almacenamiento seguro en UPLOAD_FOLDER/requests/<request_id>/.
      - Persistencia en sages.request_evidences (ruta relativa normalizada con '/').
      - Asentamiento automático de hito en la bitácora transversal (requests_trackings).
      - Registro de auditoría en BinnacleService (CARGAR_EVIDENCIA).
      - Recálculo dinámico de métricas (progreso probatorio y can_complete).

    Retorna: (success: bool, message: str, payload: dict, status_code: int)
    """
    import os
    import uuid
    import logging
    from flask import current_app, url_for
    from app.models.request_evidence_model import RequestEvidence
    from app.models.request_tracking_model import RequestTracking
    from app.utils.file_handler import save_evidence_file, FileValidationError
    from app.binnacle.services import BinnacleService
    from app.binnacle.types import AuditModule, AuditAction, AuditStatus

    logger = logging.getLogger(__name__)

    try:
        # 1. Recuperar la solicitud con sus relaciones requeridas
        req = Request.query.options(
            joinedload(Request.status),
            joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality)
        ).get(request_id)

        if not req:
            return False, "Expediente de solicitud no encontrado.", {}, 404

        # 2. Validación de Estado FSM (Solo STAT-006 activo)
        CLOSED_STATUSES = {'STAT-007', 'STAT-008', 'STAT-009'}
        status_code = req.status.status_code if req.status else ''
        if req.historical or status_code in CLOSED_STATUSES:
            return False, "El expediente se encuentra concluido o archivado. No se admiten nuevas evidencias probatorias.", {}, 422

        if status_code != 'STAT-006':
            status_label = req.status.status_name if req.status else status_code
            return False, f"Solo se pueden adjuntar evidencias en estado 'En Proceso' (estado actual: {status_label}).", {}, 422

        # 3. Control de Acceso y Titularidad (RBAC + Anti-IDOR)
        user_roles = [assoc.role.name for assoc in user.roles_assoc] if (user and user.roles_assoc) else []
        is_super = 'super_admin' in user_roles
        is_state = 'state_admin' in user_roles

        if not (is_super or is_state):
            return False, "No posee privilegios autorizados para adjuntar soportes probatorios.", {}, 403

        if is_state and not is_super:
            admin_state_id = get_admin_state_id(user)
            req_state_id = None
            try:
                req_state_id = req.institutional_staff.institution.parish.municipality.state_id
            except AttributeError:
                req_state_id = None

            if not admin_state_id or req_state_id != admin_state_id:
                return False, "Violación territorial: La solicitud pertenece a otra jurisdicción estadal.", {}, 403

            if req.attended_by_id and req.attended_by_id != user.id:
                return False, "Modo supervisión: Solo el facilitador titular asignado puede adjuntar evidencias a este expediente.", {}, 403

        # 4. Procesamiento seguro de archivo con file_handler
        sub_folder = f"requests/{request_id}"
        unique_token = uuid.uuid4().hex[:12]
        now_utc = datetime.now(timezone.utc)
        ts_str = now_utc.strftime('%Y%m%d_%H%M%S')
        custom_name = f"evidencia_{unique_token}_{ts_str}"

        try:
            evidence_data = save_evidence_file(
                file_obj=file_obj,
                sub_folder=sub_folder,
                custom_name=custom_name
            )
        except FileValidationError as fve:
            return False, str(fve), {}, 400
        except Exception as e:
            logger.error(f"Error físico al resguardar evidencia en disco (req={request_id}): {e}", exc_info=True)
            return False, "Error al escribir el archivo probatorio en el almacenamiento seguro.", {}, 500

        # 5. Persistencia en base de datos
        new_evidence = RequestEvidence(
            request_id=request_id,
            file_name=evidence_data['file_name'],
            file_path=evidence_data['file_path'].replace('\\', '/'),
            format=evidence_data['format'].upper(),
            file_weight=evidence_data['file_weight']
        )
        db.session.add(new_evidence)
        db.session.flush()

        # 6. Formateo de peso y estampa en bitácora transversal
        weight_bytes = evidence_data['file_weight']
        weight_str = f"{weight_bytes / 1024 / 1024:.2f} MB" if weight_bytes >= 1048576 else f"{weight_bytes / 1024:.1f} KB"

        user_person = user.person if user else None
        author_name = f"{user_person.first_name} {user_person.last_name}".strip() if (user_person and user_person.first_name) else (getattr(user, 'user_name', 'Facilitador UREE'))

        tracking_msg = f"Evidencia digital adjuntada por {author_name}. Archivo: {new_evidence.file_name} ({new_evidence.format}, {weight_str})."
        tracking_entry = RequestTracking(
            request_id=request_id,
            user_id=user.id,
            messages=tracking_msg,
            created_at=now_utc
        )
        db.session.add(tracking_entry)

        # 7. Auditoría en BinnacleService
        BinnacleService.create_log_entry(
            module=AuditModule.REQUESTS.value,
            action_type=AuditAction.CARGAR_EVIDENCIA.value,
            description=f"Carga de evidencia en solicitud {req.request_code}: {new_evidence.file_name} ({new_evidence.format})",
            target_table='sages.request_evidences',
            record_id=new_evidence.id,
            status=AuditStatus.COMPLETADO.value
        )

        db.session.commit()

        # 8. Recalcular métricas probatorias reactivas
        all_evidences = RequestEvidence.query.filter_by(request_id=request_id).all()
        metrics = compute_workspace_evidence_metrics(all_evidences)
        if metrics['can_complete']:
            progress_pct = 100
        else:
            progress_pct = 85 if (metrics['has_photo_evidence'] or metrics['has_pdf_evidence']) else 75
        metrics['request_progress_pct'] = progress_pct

        try:
            view_url = url_for('requests.serve_request_evidence', evidence_id=new_evidence.id)
        except RuntimeError:
            view_url = f"/requests/evidence/{new_evidence.id}/view"
        download_url = f"{view_url}?download=1"

        created_vzla = new_evidence.created_at.astimezone(timezone(timedelta(hours=-4))) if new_evidence.created_at else now_utc.astimezone(timezone(timedelta(hours=-4)))
        created_str = created_vzla.strftime('%d/%m/%Y %I:%M %p')

        payload = {
            'id': new_evidence.id,
            'request_id': request_id,
            'file_name': new_evidence.file_name,
            'file_path': new_evidence.file_path,
            'format': new_evidence.format,
            'file_weight': new_evidence.file_weight,
            'file_weight_str': weight_str,
            'created_at_str': created_str,
            'view_url': view_url,
            'download_url': download_url,
            'metrics': metrics
        }

        return True, "Evidencia digital adjuntada y custodiada exitosamente.", payload, 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Fallo no controlado en attach_request_evidence (request_id={request_id}): {e}", exc_info=True)
        return False, "Ocurrió un error inesperado al procesar la evidencia probatoria.", {}, 500


def delete_request_evidence(evidence_id: int, user) -> tuple:
    """
    Elimina de forma controlada una evidencia probatoria previamente adjuntada,
    realizando el borrado físico del archivo y asentando la traza en bitácora.
    """
    import os
    import logging
    from flask import current_app
    from app.models.request_evidence_model import RequestEvidence
    from app.models.request_tracking_model import RequestTracking
    from app.binnacle.services import BinnacleService
    from app.binnacle.types import AuditModule, AuditAction, AuditStatus

    logger = logging.getLogger(__name__)

    try:
        # 1. Recuperar evidencia y solicitud asociada
        evidence = RequestEvidence.query.options(
            joinedload(RequestEvidence.request).joinedload(Request.status),
            joinedload(RequestEvidence.request).joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality)
        ).filter_by(id=evidence_id).first()

        if not evidence:
            return False, "El registro de evidencia no fue encontrado.", {}, 404

        req = evidence.request
        if not req:
            return False, "Expediente asociado no encontrado.", {}, 404

        # 2. Control de inmutabilidad
        CLOSED_STATUSES = {'STAT-007', 'STAT-008', 'STAT-009'}
        status_code = req.status.status_code if req.status else ''
        if req.historical or status_code in CLOSED_STATUSES:
            return False, "No se pueden retirar evidencias de un expediente que ya se encuentra concluido o archivado.", {}, 422

        if status_code != 'STAT-006':
            return False, "Solo se pueden retirar evidencias en solicitudes que permanecen 'En Proceso'.", {}, 422

        # 3. Control de Acceso y Titularidad
        user_roles = [assoc.role.name for assoc in user.roles_assoc] if (user and user.roles_assoc) else []
        is_super = 'super_admin' in user_roles
        is_state = 'state_admin' in user_roles

        if not (is_super or is_state):
            return False, "No posee privilegios para retirar soportes probatorios.", {}, 403

        if is_state and not is_super:
            admin_state_id = get_admin_state_id(user)
            req_state_id = None
            try:
                req_state_id = req.institutional_staff.institution.parish.municipality.state_id
            except AttributeError:
                req_state_id = None

            if not admin_state_id or req_state_id != admin_state_id:
                return False, "Violación territorial: La solicitud pertenece a otra jurisdicción estadal.", {}, 403

            if req.attended_by_id and req.attended_by_id != user.id:
                return False, "Modo supervisión: Solo el facilitador titular asignado puede retirar evidencias de este expediente.", {}, 403

        # 4. Eliminación física en el sistema de almacenamiento
        base_upload = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        raw_path = (evidence.file_path or '').replace('\\', '/').lstrip('/')
        file_name = evidence.file_name or os.path.basename(raw_path)
        request_id = req.id
        evidence_file_name = evidence.file_name

        candidate_paths = [
            os.path.join(base_upload, raw_path),
            os.path.join(base_upload, 'requests', str(request_id), file_name)
        ]

        for cand_path in candidate_paths:
            if os.path.isfile(cand_path):
                try:
                    os.remove(cand_path)
                except OSError as oe:
                    logger.warning(f"No se pudo eliminar el archivo físico {cand_path}: {oe}")
                break

        # 5. Eliminación en base de datos
        db.session.delete(evidence)

        # 6. Asentamiento en bitácora transversal
        now_utc = datetime.now(timezone.utc)
        user_person = user.person if user else None
        author_name = f"{user_person.first_name} {user_person.last_name}".strip() if (user_person and user_person.first_name) else (getattr(user, 'user_name', 'Facilitador UREE'))

        tracking_msg = f"Evidencia digital retirada por {author_name}. Archivo: {evidence_file_name}."
        tracking_entry = RequestTracking(
            request_id=request_id,
            user_id=user.id,
            messages=tracking_msg,
            created_at=now_utc
        )
        db.session.add(tracking_entry)

        # 7. Auditoría en BinnacleService
        BinnacleService.create_log_entry(
            module=AuditModule.REQUESTS.value,
            action_type=AuditAction.ACTUALIZAR.value,
            description=f"Eliminación de evidencia en solicitud {req.request_code}: {evidence_file_name}",
            target_table='sages.request_evidences',
            record_id=evidence_id,
            status=AuditStatus.COMPLETADO.value
        )

        db.session.commit()

        # 8. Recalcular métricas probatorias actualizadas
        remaining_evidences = RequestEvidence.query.filter_by(request_id=request_id).all()
        metrics = compute_workspace_evidence_metrics(remaining_evidences)
        if metrics['can_complete']:
            progress_pct = 100
        else:
            progress_pct = 85 if (metrics['has_photo_evidence'] or metrics['has_pdf_evidence']) else 75
        metrics['request_progress_pct'] = progress_pct

        payload = {
            'deleted_evidence_id': evidence_id,
            'request_id': request_id,
            'metrics': metrics
        }

        return True, "Evidencia probatoria eliminada correctamente.", payload, 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Fallo no controlado en delete_request_evidence (evidence_id={evidence_id}): {e}", exc_info=True)
        return False, "Ocurrió un error inesperado al retirar la evidencia.", {}, 500


# ---------------------------------------------------------------------------
# Bloque Repositorio Histórico y Consulta de Expedientes Archivados (US-50)
# ---------------------------------------------------------------------------

def get_historical_requests(user: User, filters: dict = None, page: int = 1, per_page: int = 10):
    """
    Consulta paginada del repositorio centralizado de expedientes archivados (US-50).
    Aplica filtro estructural forzoso: WHERE requests.historical == TRUE y estatus de cierre
    (STAT-007: Completado, STAT-009: Cancelado).
    Aplica aislamiento multitenant según el rol del usuario (Anti-IDOR):
    - applicant: solo planteles vinculados a su usuario.
    - state_admin: solo instituciones de su estado territorial asignado (state_id).
    - super_admin: selector nacional irrestricto con pre-filtrado por sede/estado.
    Carga ansiosa profunda (joinedload) para eliminar el problema N+1.
    Retorna objeto de paginación SQLAlchemy ordenado por finished_at DESC.
    """
    from sqlalchemy import or_, and_, func
    from datetime import datetime, timedelta, timezone, date
    from app.models.request_model import Request
    from app.models.status_model import Status
    from app.models.institutional_staff_model import InstitutionalStaff
    from app.models.institution_model import Institution
    from app.models.parish_model import Parish
    from app.models.municipality_model import Municipality
    from app.models.state_model import State
    from app.models.training_model import Training
    from app.models.training_module_model import TrainingModule
    from app.models.user_model import User
    from app.models.person_model import Person

    filters = filters or {}
    user_roles = [assoc.role.name for assoc in user.roles_assoc] if (user and user.roles_assoc) else []

    # 1. Base query con JOINs requeridos
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
    )

    # 2. Filtro estructural obligatorio: Expedientes archivados (STAT-007 y STAT-009)
    query = query.filter(
        or_(
            Request.historical.is_(True),
            Status.status_code.in_(['STAT-007', 'STAT-009'])
        ),
        Status.status_code.in_(['STAT-007', 'STAT-009'])
    )

    # 3. Aislamiento por Tenancy / Rol
    if 'applicant' in user_roles and 'super_admin' not in user_roles and 'state_admin' not in user_roles:
        if not user.person or not user.person.institutional_staff:
            return Request.query.filter(Request.id == -1).paginate(page=1, per_page=per_page, error_out=False)
        user_inst_id = user.person.institutional_staff[0].institution_id
        query = query.filter(InstitutionalStaff.institution_id == user_inst_id)

    elif 'state_admin' in user_roles and 'super_admin' not in user_roles:
        admin_state_id = get_admin_state_id(user)
        if not admin_state_id:
            return Request.query.filter(Request.id == -1).paginate(page=1, per_page=per_page, error_out=False)
        query = query.filter(Municipality.state_id == admin_state_id)

    elif 'super_admin' in user_roles:
        # Super admin puede filtrar opcionalmente por estado
        state_filter = filters.get('state_id')
        if state_filter and str(state_filter).isdigit() and int(state_filter) > 0:
            query = query.filter(Municipality.state_id == int(state_filter))

    # 4. Filtros opcionales de interfaz
    # Filtro por Estatus (si el usuario elige específicamente Completado o Cancelado)
    status_filter = filters.get('status') or filters.get('status_code')
    if status_filter:
        if str(status_filter).isdigit():
            query = query.filter(Request.status_id == int(status_filter))
        elif status_filter in ('STAT-007', 'STAT-009'):
            query = query.filter(Status.status_code == status_filter)

    # Filtro por Municipio
    mun_filter = filters.get('municipality_id')
    if mun_filter and str(mun_filter).isdigit():
        query = query.filter(Municipality.id == int(mun_filter))

    # Filtro por Módulo / Tema Formativo
    module_filter = filters.get('module_id')
    if module_filter and str(module_filter).isdigit():
        query = query.filter(Training.training_module_id == int(module_filter))

    training_filter = filters.get('training_id')
    if training_filter and str(training_filter).isdigit():
        query = query.filter(Training.id == int(training_filter))

    # Filtro de Búsqueda de Texto
    search_query = (filters.get('search') or '').strip()
    if search_query:
        pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Institution.institution_name.ilike(pattern),
                Institution.plantel_code.ilike(pattern),
                Request.request_code.ilike(pattern),
                Training.name.ilike(pattern),
                Municipality.name.ilike(pattern)
            )
        )

    # Filtros de Rango de Fecha (finished_at)
    date_from = filters.get('date_from')
    if date_from:
        try:
            if isinstance(date_from, str):
                df = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                df = date_from
            query = query.filter(Request.finished_at >= df)
        except Exception:
            pass

    date_to = filters.get('date_to')
    if date_to:
        try:
            if isinstance(date_to, str):
                dt = (datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)).replace(tzinfo=timezone.utc)
            else:
                dt = date_to + timedelta(days=1)
            query = query.filter(Request.finished_at < dt)
        except Exception:
            pass

    # 5. Carga ansiosa profunda (joinedload) para evitar N+1
    query = query.options(
        joinedload(Request.status),
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.person),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.institution_type),
        joinedload(Request.attended_by).joinedload(User.person)
    )

    # 6. Ordenamiento y Paginación
    return query.order_by(
        Request.finished_at.desc().nullslast(),
        Request.id.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)


def get_historical_request_detail(request_id: int, user: User) -> dict:
    """
    Obtiene la ficha técnica histórica integral de solo lectura de una solicitud archivada (US-50).
    Aplica carga ansiosa profunda (joinedload) sobre todas las relaciones satélites.
    Verifica los permisos territoriales e institucionales del usuario solicitante.
    """
    from flask import abort, url_for
    from app.models.request_model import Request
    from app.models.training_module_model import TrainingModule
    from app.models.person_model import Person
    from app.models.request_evidence_model import RequestEvidence
    from app.models.request_tracking_model import RequestTracking
    from app.models.request_justification_model import RequestJustification
    from app.models.rating_model import Rating
    from app.utils.qr_generator import generate_verification_token
    from datetime import datetime, timezone, timedelta

    req = db.session.query(Request).options(
        joinedload(Request.status),
        joinedload(Request.training).joinedload(Training.training_module),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.person),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.institution_type),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.institution_scope),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.institution).joinedload(Institution.institution_dependency),
        joinedload(Request.institutional_staff).joinedload(InstitutionalStaff.position),
        joinedload(Request.attended_by).joinedload(User.person),
        joinedload(Request.plannings),
        joinedload(Request.justifications).joinedload(RequestJustification.reason),
        joinedload(Request.evidences),
        joinedload(Request.tracking_steps).joinedload(RequestTracking.user).joinedload(User.person),
        joinedload(Request.ratings)
    ).filter(Request.id == request_id).first_or_404()

    # Validar que sea un expediente archivado
    status_code = req.status.status_code if req.status else ''
    if status_code not in ('STAT-007', 'STAT-009') and not req.historical:
        abort(400, description="El expediente seleccionado aún no se encuentra archivado en el histórico.")

    # Validar Aislamiento Territorial / Tenancy
    user_roles = [assoc.role.name for assoc in user.roles_assoc] if (user and user.roles_assoc) else []
    if 'applicant' in user_roles and 'super_admin' not in user_roles and 'state_admin' not in user_roles:
        user_inst_id = user.person.institutional_staff[0].institution_id if (user.person and user.person.institutional_staff) else None
        req_inst_id = req.institutional_staff.institution_id if req.institutional_staff else None
        if user_inst_id != req_inst_id:
            abort(403, description="Acceso denegado: No tiene permisos sobre este expediente institucional.")
    elif 'state_admin' in user_roles and 'super_admin' not in user_roles:
        admin_state_id = get_admin_state_id(user)
        try:
            req_state_id = req.institutional_staff.institution.parish.municipality.state_id
        except AttributeError:
            req_state_id = None
        if admin_state_id != req_state_id:
            abort(403, description="Violación de Acceso: El expediente pertenece a otra jurisdicción territorial.")

    vzla_tz = timezone(timedelta(hours=-4))
    finished_vzla = req.finished_at.astimezone(vzla_tz) if req.finished_at else (req.updated_at.astimezone(vzla_tz) if req.updated_at else None)

    # Identificación institucional
    staff = req.institutional_staff
    inst = staff.institution if staff else None
    institution_data = {
        'name': inst.institution_name if inst else 'N/A',
        'code_dea': inst.plantel_code if (inst and hasattr(inst, 'plantel_code')) else 'N/A',
        'state': inst.parish.municipality.state.name if (inst and inst.parish and inst.parish.municipality and inst.parish.municipality.state) else 'N/A',
        'municipality': inst.parish.municipality.name if (inst and inst.parish and inst.parish.municipality) else 'N/A',
        'parish': inst.parish.name if (inst and inst.parish) else 'N/A',
        'address': inst.address if inst else 'N/A',
        'type': inst.institution_type.name if (inst and inst.institution_type) else 'Educativo',
        'contact_person': f"{staff.person.first_name} {staff.person.last_name}" if (staff and staff.person) else 'N/A',
        'position': staff.position.name if (staff and staff.position) else 'Directivo'
    }

    # Datos pedagógicos
    training = req.training
    pedagogical_data = {
        'module_name': training.training_module.name if (training and training.training_module) else 'N/A',
        'training_name': training.name if training else 'N/A',
        'description': req.description or 'Sin justificación registrada.'
    }

    # Facilitador responsable
    attended_user = req.attended_by
    if attended_user and attended_user.person:
        p = attended_user.person
        facilitator_data = {
            'name': f"{p.first_name} {p.last_name}".strip(),
            'phone': p.mobile or p.phone or 'No registrado',
            'email': p.email or 'No registrado',
            'role': 'Coordinador / Facilitador UREE'
        }
    else:
        facilitator_data = {
            'name': 'Personal Técnico CORPOELEC',
            'phone': 'N/A',
            'email': 'N/A',
            'role': 'Coordinación UREE'
        }

    # Datos de Cancelación (STAT-009)
    cancellation_data = None
    if status_code == 'STAT-009' or req.historical:
        for just in req.justifications:
            if just.justification_type in ('CANCELACION_ADMIN', 'CANCELACION_SOLICITANTE'):
                cancellation_data = {
                    'type': just.justification_type,
                    'type_label': 'Cancelación Administrativa por Coordinación' if just.justification_type == 'CANCELACION_ADMIN' else 'Desistimiento Voluntario del Plantel',
                    'reason': just.reason.name if just.reason else 'Causa de fuerza mayor',
                    'justification': just.justification,
                    'created_at': finished_vzla
                }
                break

    # Evidencias custodiadas con URLs seguras
    evidences_list = []
    for ev_idx, ev in enumerate(req.evidences or [], 1):
        fmt = (ev.format or '').upper()
        if fmt == 'JPEG':
            fmt = 'JPG'
        is_img = fmt in ('JPG', 'JPEG', 'PNG', 'WEBP')
        is_pdf = fmt == 'PDF'

        weight = ev.file_weight or 0
        if weight >= 1024 * 1024:
            weight_str = f"{weight / (1024 * 1024):.2f} MB"
        else:
            weight_str = f"{max(1, round(weight / 1024))} KB"

        # Limpieza de nombre de archivo institucional (cero códigos técnicos o hashes de BD)
        import re as _re, os as _os
        raw_name = (ev.file_name or '').strip()
        base, ext_part = _os.path.splitext(raw_name)
        if not ext_part and fmt:
            ext_part = '.' + fmt.lower()

        # Caso 1: Si viene con prefijo hash o UUID seguido de guion bajo
        parts = base.split('_', 1)
        if len(parts) == 2 and _re.match(r'^[0-9a-fA-F\-]{8,}$', parts[0]):
            clean_name = parts[1] + ext_part
        else:
            clean_name = raw_name

        # Caso 2: Si el nombre base es un hash, código puramente numérico o término genérico
        clean_base, clean_ext = _os.path.splitext(clean_name)
        if (
            not clean_name
            or clean_base.isdigit()
            or _re.match(r'^[0-9a-fA-F\-]{8,}$', clean_base)
            or clean_base.lower() in ('file', 'evidence', 'soporte', 'upload', 'blob', 'image', 'imagen', 'documento', 'archivo')
        ):
            ext_label = clean_ext if clean_ext else ext_part
            clean_name = f"Soporte Documental N°{ev_idx}{ext_label}"

        display_filename = clean_name

        evidences_list.append({
            'id': ev.id,
            'file_name': display_filename,
            'format': fmt,
            'file_weight': weight,
            'file_weight_str': weight_str,
            'is_image': is_img,
            'is_pdf': is_pdf,
            'created_at': ev.created_at.astimezone(vzla_tz) if ev.created_at else None,
            'view_url': url_for('requests.serve_request_evidence', evidence_id=ev.id),
            'download_url': url_for('requests.serve_request_evidence', evidence_id=ev.id) + '?download=1'
        })

    # Datos de Cierre y Planificación
    active_plan = None
    if req.plannings:
        plans = [p for p in req.plannings if p.planned_for]
        if plans:
            active_plan = max(plans, key=lambda p: p.planned_for)

    # Evaluación y Encuesta (Rating)
    rating_data = None
    if req.ratings:
        r = req.ratings[0]
        rating_data = {
            'score': r.score,
            'score_activity': r.score_activity,
            'score_instructor': r.score_instructor,
            'score_admin_response': r.score_admin_response,
            'comment': r.comment
        }

    token = generate_verification_token(req.request_code, req.id)
    token_display = f"{token[:4].upper()}-{token[4:8].upper()}-{token[8:12].upper()}-{token[12:16].upper()}"

    # Resumen consolidado de la labor formativa
    summary_text = (
        f"Jornada de formación comunitaria en {pedagogical_data['training_name']} impartida a la comunidad "
        f"educativa de {institution_data['name']}. Actividad coordinada y certificada por la División de Uso "
        f"Racional y Eficiente de la Energía (UREE) de CORPOELEC."
    )

    return {
        'request': req,
        'institution_data': institution_data,
        'pedagogical_data': pedagogical_data,
        'facilitator_data': facilitator_data,
        'cancellation_data': cancellation_data,
        'evidences': evidences_list,
        'active_plan': active_plan,
        'rating_data': rating_data,
        'finished_at_vzla': finished_vzla,
        'summary_text': summary_text,
        'token': token,
        'token_display': token_display,
        'can_download_report': (status_code == 'STAT-007'),
        'timeline_steps': get_request_timeline(request_id)
    }

