from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.decorators.auth_decorators import role_required, check_permissions
from app.requests import requests_bp
from app.requests.services import get_applicant_active_requests
from app.models.user_model import User
from app.extensions import limiter

# ---------------------------------------------------------------------------
# Ruta Solicitante: Mis Solicitudes
# ---------------------------------------------------------------------------

@requests_bp.route('/my-requests', methods=['GET'])
@login_required
@role_required('applicant')
@check_permissions('create_request')
def applicant_dashboard():
    """
    Renderiza el panel de control y bandeja de solicitudes activas
    para el representante de la institución educativa.
    """
    # Obtenemos las solicitudes desde el servicio
    active_requests = get_applicant_active_requests(current_user.id)
    
    # Validamos si la institución educativa está activa (diferente a STAT-002)
    # para enviar una bandera a la plantilla y deshabilitar botones si es necesario
    institution_active = True
    user = User.query.get(current_user.id)
    
    if user and user.person and user.person.institutional_staff:
        institution = user.person.institutional_staff[0].institution
        if institution and institution.status:
            institution_active = (institution.status.status_code != 'STAT-002')
    
    return render_template(
        'requests/applicant_dashboard.html',
        requests=active_requests,
        institution_active=institution_active
    )
# ---------------------------------------------------------------------------
# Ruta Solicitante: Registrar Nueva Solicitud
# ---------------------------------------------------------------------------

@requests_bp.route('/new', methods=['GET'])
@login_required
@role_required('applicant')
@check_permissions('create_request')
def new_request_wizard():
    """
    Renderiza el wizard de 3 pasos (US-34) para registrar una solicitud.
    Filtra módulos activos e inyecta la data institucional segura.
    """
    from app.models.training_module_model import TrainingModule
    from app.requests.forms import NewRequestWizardForm

    user = User.query.get(current_user.id)
    if not user or not user.person or not user.person.institutional_staff:
        return "Acceso denegado: Institución no vinculada.", 403
        
    institution = user.person.institutional_staff[0].institution
    if not institution or institution.status.status_code == 'STAT-002':
        return "Acceso denegado: Institución inactiva.", 403

    form = NewRequestWizardForm()
    
    # Módulos rectores activos para el Paso 1
    active_modules = TrainingModule.query.filter_by(is_active=True).order_by(TrainingModule.order_index).all()
    
    return render_template(
        'requests/new_request_wizard.html',
        form=form,
        modules=active_modules,
        staff=user.person.institutional_staff[0]
    )

# ---------------------------------------------------------------------------
# Ruta Solicitante: Validación de Duplicidad de Solicitud
# ---------------------------------------------------------------------------

@requests_bp.route('/api/check-duplicity', methods=['POST'])
@login_required
@role_required('applicant')
@check_permissions('create_request')
@limiter.limit("20 per minute", methods=["POST"], key_func=lambda: str(current_user.id))
def check_duplicity():
    """
    Endpoint AJAX para validación preventiva de duplicidad.
    Devuelve HTTP 200 con payload {is_duplicate: true/false}.
    """
    from flask import request, jsonify
    from app.requests.services import check_request_duplicity
    
    data = request.get_json() or {}
    training_id = data.get('training_id')
    
    if not training_id:
        return jsonify({'error': 'training_id requerido'}), 400
        
    user = User.query.get(current_user.id)
    if not user or not user.person or not user.person.institutional_staff:
        return jsonify({'error': 'Usuario no autorizado'}), 403
        
    institution_id = user.person.institutional_staff[0].institution_id
    
    # Invocamos la lógica de servicio arquitectónicamente correcta
    result = check_request_duplicity(institution_id, int(training_id))
    return jsonify(result), 200

# ---------------------------------------------------------------------------
# Ruta Solicitante: Enviar Nueva Solicitud
# ---------------------------------------------------------------------------

@requests_bp.route('/submit-new', methods=['POST'])
@login_required
@role_required('applicant')
@check_permissions('create_request')
@limiter.limit("10 per minute", methods=["POST"], key_func=lambda: str(current_user.id))
def submit_new_request():
    """
    Endpoint AJAX para recibir y procesar el payload del asistente en formato JSON.
    Protegido contra Spam mediante Flask-Limiter.
    """
    from flask import request, jsonify
    from app.requests.forms import NewRequestWizardForm
    from app.requests.services import create_training_request
    from app.models.training_model import Training

    data = request.get_json() or {}
    
    # Instanciamos WTForms omitiendo CSRF nativo del formulario (Se asume validación global por CSRFProtect)
    form = NewRequestWizardForm(data=data, meta={'csrf': False})
    
    # Validamos contra la Base de Datos inyectando el choice dinámicamente si existe.
    submitted_id = data.get('training_id')
    if submitted_id:
        training = Training.query.get(submitted_id)
        if training:
            form.training_id.choices = [(training.id, training.name)]
        else:
            form.training_id.choices = []
    else:
        form.training_id.choices = []
    
    if not form.validate():
        # Extraer el primer error de validación
        errors = [msg for field in form.errors.values() for msg in field]
        return jsonify({'success': False, 'message': errors[0] if errors else "Datos inválidos."}), 400
        
    # Invocamos al servicio transaccional
    success, message, req_id = create_training_request(
        user_id=current_user.id,
        training_id=form.training_id.data,
        description=form.description.data
    )
    
    if success:
        return jsonify({'success': True, 'message': message, 'request_id': req_id}), 201
    else:
        return jsonify({'success': False, 'message': message}), 400

# ---------------------------------------------------------------------------
# Ruta Solicitante: Descarga Directa del Comprobante PDF (US-36)
# ---------------------------------------------------------------------------

@requests_bp.route('/download-ticket/<int:request_id>', methods=['GET'])
@login_required
@role_required('applicant')
@check_permissions('create_request')
def download_receipt_ticket(request_id):
    """
    Genera y descarga el comprobante en PDF al vuelo.
    Cuenta con protección estricta IDOR: Un solicitante solo puede descargar tickets de su propio plantel.
    """
    from flask import send_file, abort
    from app.models.request_model import Request
    from app.utils.pdf_generator import generate_receipt_ticket_pdf
    
    # Extraer el usuario en sesión y su plantel
    user = User.query.get(current_user.id)
    if not user or not user.person or not user.person.institutional_staff:
        abort(403, description="No posee afiliación institucional válida.")
        
    session_institution_id = user.person.institutional_staff[0].institution_id
    
    # 1. Buscar la solicitud
    req = Request.query.get_or_404(request_id)
    
    # 2. Protección IDOR: Validar que el plantel de la solicitud sea el mismo del usuario
    request_institution_id = req.institutional_staff.institution_id
    if session_institution_id != request_institution_id:
        abort(403, description="Acceso denegado: No tiene permisos para descargar este documento institucional.")
        
    # 3. Compilación del PDF en memoria
    try:
        pdf_buffer, _ = generate_receipt_ticket_pdf(req)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Comprobante_{req.request_code}.pdf"
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error sirviendo el PDF de la solicitud {req.request_code}: {e}")
        abort(500, description="Error interno al generar el documento. Intente nuevamente.")


# ---------------------------------------------------------------------------
# Ruta Administrador Estadal: Bandeja Territorial de Solicitudes (US-39)
# ---------------------------------------------------------------------------

@requests_bp.route('/state-dashboard', methods=['GET'])
@login_required
@role_required('state_admin')
@check_permissions('manage_requests')
def state_admin_dashboard():
    """
    Renderiza el centro de mando regional para el administrador estadal.
    Aplica aislamiento estricto por Estado (Capa de Seguridad) y clasifica 
    los expedientes por semáforo de prioridad lógica (Business Logic Sorting).
    """
    from flask import request, render_template, abort, flash
    from app.requests.services import get_admin_state_id, get_state_dashboard_metrics, get_state_requests_paginated
    
    # 1. Extracción de Jurisdicción Inmutable
    # Evita que el administrador intente inyectar '?state_id=5' en la URL.
    state_id = get_admin_state_id(current_user)
    if not state_id:
        flash("Acceso denegado: Su perfil no posee una asignación territorial válida (Estado).", "danger")
        abort(403)
        
    # 2. Captura de Parámetros GET (Paginación y Filtros Reactivos)
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '', type=str)
    status_id = request.args.get('status', None, type=int)
    municipality_id = request.args.get('municipality', None, type=int)
    
    # 3. Consulta Masiva de KPIs Regionales
    metrics = get_state_dashboard_metrics(state_id)
    
    # 4. Consulta Paginada de Expedientes
    per_page = min(request.args.get('per_page', 10, type=int), 50)
    
    pagination = get_state_requests_paginated(
        state_id=state_id, 
        page=page, 
        per_page=per_page, 
        search_query=search_query,
        status_id=status_id,
        municipality_id=municipality_id
    )
    
    # 5. Respuesta Dual (Soporte para recarga asíncrona o primera carga completa)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax'):
        # Retorna un fragmento (Partial) solo con los <tr> para el Fetch JS
        return render_template('requests/partials/_state_dashboard_table.html', pagination=pagination)
        
    # Consultas auxiliares para llenar los `<select>` de filtros
    from app.models.status_model import Status
    from app.models.municipality_model import Municipality
    
    # Obtener estatus relevantes para solicitudes (STAT-003 al STAT-009)
    available_statuses = Status.query.filter(
        Status.status_code.in_(['STAT-003', 'STAT-004', 'STAT-005', 'STAT-006', 'STAT-007', 'STAT-008', 'STAT-009'])
    ).all()
    
    # Obtener municipios de la jurisdicción actual
    available_municipalities = Municipality.query.filter_by(state_id=state_id).order_by(Municipality.name.asc()).all()

    # Primera carga de la página
    return render_template(
        'requests/state_dashboard.html',
        metrics=metrics,
        pagination=pagination,
        search_query=search_query,
        current_status=status_id,
        current_municipality=municipality_id,
        statuses=available_statuses,
        municipalities=available_municipalities,
        user_state=current_user.person.company_staff[0].place.parish.municipality.state.name
    )

# ---------------------------------------------------------------------------
# Ruta Administrador Estadal: Vista Detallada de Solicitud (Ficha Técnica)
# ---------------------------------------------------------------------------

@requests_bp.route('/<int:id>/detail', methods=['GET'])
@login_required
@role_required('state_admin', 'super_admin')
@check_permissions('manage_requests')
def state_request_detail(id):
    """
    Renderiza la Ficha Técnica Individual / Expediente.
    Accesible para Administrador Estadal (con aislamiento territorial)
    y para Super Administrador (cobertura nacional).
    """
    from flask import render_template, abort, flash, redirect, url_for
    from app.requests.services import get_admin_state_id, get_request_full_detail
    
    user_roles = [assoc.role.name for assoc in current_user.roles_assoc] if current_user and current_user.roles_assoc else []
    is_super_admin = 'super_admin' in user_roles

    # 1. Extraer la jurisdicción inmutable si es Administrador Estadal
    admin_state_id = None
    if not is_super_admin:
        admin_state_id = get_admin_state_id(current_user)
        if not admin_state_id:
            flash("Acceso denegado: Su perfil no posee una asignación territorial válida.", "danger")
            abort(403)
        
    # 2. Cargar la radiografía completa del expediente
    # Lanza 404 de manera nativa si la solicitud no existe.
    req = get_request_full_detail(id)
    
    # 3. Escudo Territorial Transversal para Administrador Estadal
    if not is_super_admin:
        req_state_id = req.institutional_staff.institution.parish.municipality.state_id
        if req_state_id != admin_state_id:
            flash("Violación de Acceso: El expediente solicitado pertenece a otra jurisdicción territorial.", "danger")
            abort(403)
        
        # 4. Regla de Negocio: Exclusión de Trámites Cerrados en consola operativa estadal
        if req.historical:
            flash("Este expediente ya se encuentra cerrado (Histórico) y no admite más gestiones operativas.", "warning")
            return redirect(url_for('requests.state_admin_dashboard'))
        
    return render_template('requests/state_request_detail.html', req=req)

# ---------------------------------------------------------------------------
# Bloque Administrador Estadal: Tomar Solicitud
# ---------------------------------------------------------------------------

@requests_bp.route('/api/requests/<int:request_id>/claim-and-attend', methods=['POST'])
@login_required
@role_required('state_admin')
@check_permissions('manage_requests')
def api_claim_and_attend(request_id):
    """
    Endpoint para que un administrador estadal asuma una solicitud.
    Verifica jurisdicción, controla concurrencia (409) y responde HTTP codes según estándar.
    """
    from flask import jsonify
    from app.requests.services import claim_and_attend_request, RequestAlreadyClaimedException, get_admin_state_id
    from app.models.request_model import Request

    # 1. Validación de territorio (In-line security)
    req = Request.query.get(request_id)
    if not req:
        return jsonify({'success': False, 'message': 'Solicitud no encontrada.'}), 404
        
    admin_state_id = get_admin_state_id(current_user)
    
    try:
        req_state_id = req.institutional_staff.institution.parish.municipality.state_id
    except AttributeError:
        req_state_id = None

    if not admin_state_id or req_state_id != admin_state_id:
        return jsonify({'success': False, 'message': 'Acceso denegado. Jurisdicción no válida para este operador.'}), 403

    # 2. Delegar a capa de servicios (Transaccional)
    try:
        success, msg, data = claim_and_attend_request(request_id, current_user)
        if success:
            return jsonify({'success': True, 'message': msg, 'data': data}), 200
        else:
            return jsonify({'success': False, 'message': msg}), 400
    except RequestAlreadyClaimedException as e:
        return jsonify({'success': False, 'message': str(e)}), 409
    except Exception as e:
        import logging
        logging.error(f"Error en claim-and-attend (Request ID {request_id}): {e}")
        return jsonify({'success': False, 'message': 'Error interno al procesar la asignación.'}), 500

# ---------------------------------------------------------------------------  
# Ruta Super Administrador: Tablero de Monitoreo Nacional (US-38)
# ---------------------------------------------------------------------------

@requests_bp.route('/national-monitoring', methods=['GET'])
@login_required
@role_required('super_admin')
@check_permissions('manage_requests')
def national_monitoring():
    """
    Renderiza el Tablero de Monitoreo Nacional con semáforo y pre-filtrado (US-38)
    para el Super Administrador.
    """
    from flask import request
    from app.models.state_model import State
    from app.models.training_module_model import TrainingModule
    from app.models.status_model import Status
    from app.requests.services import get_national_monitoring_data

    # 1. Resolución de Estado (Pre-filtrado inteligente vs Selección explícita)
    # Si 'state_id' no está en request.args (primera carga / acceso inicial),
    # se preselecciona la sede corporativa del Super Administrador.
    user = User.query.get(current_user.id)
    default_state_id = None
    if user and user.person and user.person.company_staff:
        try:
            default_state_id = user.person.company_staff[0].place.parish.municipality.state_id
        except (IndexError, AttributeError):
            default_state_id = None

    if 'state_id' not in request.args:
        # Primera carga: asignar sede corporativa
        selected_state_id = default_state_id
        state_filter_val = str(default_state_id) if default_state_id else 'all'
    else:
        raw_state = request.args.get('state_id', '').strip()
        if raw_state in ('', 'all', '0'):
            selected_state_id = None
            state_filter_val = 'all'
        elif raw_state.isdigit():
            selected_state_id = int(raw_state)
            state_filter_val = str(selected_state_id)
        else:
            selected_state_id = None
            state_filter_val = 'all'

    # 2. Otros filtros y paginación
    search = request.args.get('search', '').strip()
    raw_module = request.args.get('module_id', '').strip()
    module_id = int(raw_module) if raw_module.isdigit() else None
    
    raw_status = request.args.get('status_id', '').strip()
    status_id = int(raw_status) if raw_status.isdigit() else (raw_status if raw_status else None)
    
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
        
    try:
        per_page = min(max(1, int(request.args.get('per_page', 10))), 50)
    except (ValueError, TypeError):
        per_page = 10

    # 3. Invocar servicio de agregación y filtrado
    data = get_national_monitoring_data(
        state_id=selected_state_id,
        search=search,
        module_id=module_id,
        status_id=status_id,
        page=page,
        per_page=per_page
    )

    # 4. Catálogos para selectores
    states = State.query.order_by(State.name.asc()).all()
    modules = TrainingModule.query.filter_by(is_active=True).order_by(TrainingModule.order_index).all()
    statuses = Status.query.filter(Status.context.like('%Solicitudes%')).order_by(Status.id.asc()).all()

    # Filtros actuales para la vista
    active_filters = {
        'state_id': state_filter_val,
        'search': search,
        'module_id': raw_module,
        'status_id': raw_status,
        'per_page': per_page
    }

    return render_template(
        'requests/national_monitoring.html',
        kpis=data['kpis'],
        pagination=data['pagination'],
        requests=data['requests'],
        states=states,
        modules=modules,
        statuses=statuses,
        filters=active_filters,
        default_state_id=default_state_id
    )


# ---------------------------------------------------------------------------
# Rutas Super Administrador: Auditoría de Retrasos SLA y Exigencia Coercitiva (US-38-act2)
# ---------------------------------------------------------------------------

@requests_bp.route('/delays-audit', methods=['GET'])
@login_required
@role_required('super_admin')
@check_permissions('manage_requests')
def delays_audit():
    """
    Renderiza el Panel de Auditoría de Retrasos SLA (Vista A.2)
    para el Super Administrador. Centraliza los expedientes con infracciones normativas
    (>72h en atención inicial o >10 días en ejecución presencial).
    """
    from app.models.state_model import State
    from app.requests.services import get_delays_audit_data

    # 1. Resolución de Estado (Pre-filtrado inteligente vs Selección explícita)
    user = User.query.get(current_user.id)
    default_state_id = None
    if user and user.person and user.person.company_staff:
        try:
            default_state_id = user.person.company_staff[0].place.parish.municipality.state_id
        except (IndexError, AttributeError):
            default_state_id = None

    if 'state_id' not in request.args:
        selected_state_id = default_state_id
        state_filter_val = str(default_state_id) if default_state_id else 'all'
    else:
        raw_state = request.args.get('state_id', '').strip()
        if raw_state in ('', 'all', '0'):
            selected_state_id = None
            state_filter_val = 'all'
        elif raw_state.isdigit():
            selected_state_id = int(raw_state)
            state_filter_val = str(selected_state_id)
        else:
            selected_state_id = None
            state_filter_val = 'all'

    # 2. Filtro por estatus de descargo (all, unjustified, justified)
    justification_status = request.args.get('justification_status', 'all').strip()
    if justification_status not in ('all', 'unjustified', 'justified'):
        justification_status = 'all'

    # 3. Búsqueda y paginación
    search = request.args.get('search', '').strip()

    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = min(max(1, int(request.args.get('per_page', 10))), 50)
    except (ValueError, TypeError):
        per_page = 10

    # 4. Invocar servicio
    data = get_delays_audit_data(
        user=user,
        state_id=selected_state_id,
        justification_status=justification_status,
        search=search,
        page=page,
        per_page=per_page
    )

    # 5. Catálogo de Estados para el selector
    states = State.query.order_by(State.name.asc()).all()

    active_filters = {
        'state_id': state_filter_val,
        'justification_status': justification_status,
        'search': search,
        'per_page': per_page
    }

    return render_template(
        'requests/delays_audit.html',
        kpis=data['kpis'],
        pagination=data['pagination'],
        requests=data['requests'],
        states=states,
        filters=active_filters,
        default_state_id=default_state_id
    )


@requests_bp.route('/api/delays/<int:request_id>/justification', methods=['GET'])
@login_required
@role_required('super_admin')
@check_permissions('manage_requests')
def get_delay_justification(request_id):
    """
    Endpoint AJAX para obtener los detalles de la justificación técnica de mora.
    Retorna JSON { request_code, institution_name, reason_name, submitted_by, created_at, justification_text, justification_type }.
    """
    from app.requests.services import get_request_justification_detail

    detail = get_request_justification_detail(request_id)
    if not detail:
        return jsonify({'error': 'No se encontró un descargo formal registrado para este expediente.'}), 404

    return jsonify(detail), 200


@requests_bp.route('/api/delays/<int:request_id>/demand-response', methods=['POST'])
@login_required
@role_required('super_admin')
@check_permissions('manage_requests')
@limiter.limit("1 per hour", methods=["POST"], key_func=lambda: f"demand_delay_{current_user.id}_{request.view_args.get('request_id')}")
def demand_delay_response_endpoint(request_id):
    """
    Endpoint AJAX con rate limiting estricto (máx. 1 por hora por solicitud/usuario)
    para registrar la exigencia formal en el tracking de la solicitud.
    """
    from app.requests.services import demand_delay_response

    success, message, status_code = demand_delay_response(request_id, current_user)
    return jsonify({'success': success, 'message': message}), status_code


# ---------------------------------------------------------------------------
# Ruta Compartida: Endpoint API de Agenda Mensual (/requests/api/calendar-events)
# ---------------------------------------------------------------------------

@requests_bp.route('/api/calendar-events', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
@check_permissions('manage_requests')
def calendar_events_endpoint():
    """
    Endpoint JSON que retorna las formaciones agendadas para el mes y año solicitados.
    Parámetros GET:
      - year: int (ej. 2026, por defecto año actual)
      - month: int (1-12, por defecto mes actual)
      - state_id: int opcional (interpretado únicamente si el usuario es super_admin)
    Diferencia rol y aplica aislamiento territorial estricto sin registrar auditorías ni notificaciones.
    """
    from datetime import datetime, timezone
    from flask import request, jsonify
    from app.requests.services import get_monthly_calendar_events

    now = datetime.now(timezone.utc)
    
    # Parsear y validar 'year'
    try:
        year = int(request.args.get('year', now.year))
        if year < 2000 or year > 2100:
            year = now.year
    except (ValueError, TypeError):
        year = now.year

    # Parsear y validar 'month'
    try:
        month = int(request.args.get('month', now.month))
        if month < 1 or month > 12:
            month = now.month
    except (ValueError, TypeError):
        month = now.month

    # Filtro opcional de state_id
    raw_state_id = request.args.get('state_id', '').strip()
    state_id = int(raw_state_id) if raw_state_id.isdigit() else None

    # Invocar servicio desacoplado
    data = get_monthly_calendar_events(
        user=current_user,
        year=year,
        month=month,
        state_id=state_id
    )

    return jsonify(data), 200

# ---------------------------------------------------------------------------
# SLA Gate: Catálogo de Razones para el Modal Bloqueante
# ---------------------------------------------------------------------------

@requests_bp.route('/api/requests/<int:request_id>/delay-reasons', methods=['GET'])
@login_required
@role_required('state_admin')
@check_permissions('manage_requests')
def get_delay_reasons_for_request(request_id):
    """
    Endpoint AJAX que devuelve el catálogo de razones disponibles
    para justificar una mora ANS en la Ficha Técnica (SLA Gate Modal).
    """
    from app.requests.services import get_delay_reasons
    reasons = get_delay_reasons()
    return jsonify({'reasons': reasons}), 200


# ---------------------------------------------------------------------------
# SLA Gate: Registrar Descargo Obligatorio de Retraso
# ---------------------------------------------------------------------------

@requests_bp.route('/api/requests/<int:request_id>/justify-delay', methods=['POST'])
@login_required
@role_required('state_admin')
@check_permissions('manage_requests')
@limiter.limit("2 per hour", methods=["POST"], key_func=lambda: f"justify_delay_{current_user.id}_{request.view_args.get('request_id')}")
@limiter.limit("1 per minute", methods=["POST"], key_func=lambda: f"justify_delay_{current_user.id}_{request.view_args.get('request_id')}")
@limiter.limit("5 per hour", methods=["POST"], key_func=lambda: f"justify_delay_user_{current_user.id}")
def justify_delay(request_id):
    """
    Endpoint AJAX (SLA Gate) para registrar el descargo formal de mora ANS.
    Cuenta con rate limit estricto por usuario y solicitud para mitigar spam.
    Requiere reason_id (int) y justification (str, mínimo 20 caracteres).
    Al completarse exitosamente, el bloqueo operativo de la solicitud se levanta.
    """
    from app.requests.services import submit_delay_justification

    data = request.get_json() or {}
    reason_id = data.get('reason_id')
    justification_text = data.get('justification', '')

    if not reason_id:
        return jsonify({'success': False, 'message': 'Debe seleccionar una razón de retraso.'}), 400

    try:
        reason_id = int(reason_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'reason_id inválido.'}), 400

    success, message, status_code = submit_delay_justification(
        request_id=request_id,
        admin_user=current_user,
        reason_id=reason_id,
        justification_text=justification_text
    )

    return jsonify({'success': success, 'message': message}), status_code
