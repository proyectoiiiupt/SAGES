from flask import render_template
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
@role_required('state_admin')
@check_permissions('manage_requests')
def state_request_detail(id):
    """
    Renderiza la Ficha Técnica Individual.
    Carga toda la información de la solicitud.
    """
    from flask import render_template, abort, flash, redirect, url_for
    from app.requests.services import get_admin_state_id, get_request_full_detail
    
    # 1. Extraer la jurisdicción inmutable del Administrador en sesión
    admin_state_id = get_admin_state_id(current_user)
    if not admin_state_id:
        flash("Acceso denegado: Su perfil no posee una asignación territorial válida.", "danger")
        abort(403)
        
    # 2. Cargar la radiografía completa del expediente
    # Lanza 404 de manera nativa si la solicitud no existe.
    req = get_request_full_detail(id)
    
    # 3. Escudo Territorial Transversal
    # Compara el Estado de la Institución solicitante contra el Estado del Administrador.
    req_state_id = req.institutional_staff.institution.parish.municipality.state_id
    if req_state_id != admin_state_id:
        flash("Violación de Acceso: El expediente solicitado pertenece a otra jurisdicción territorial.", "danger")
        abort(403)
        
    # 4. Regla de Negocio: Exclusión de Trámites Cerrados
    # La consola operativa no gestiona históricos. Si ya culminó o se canceló, se deniega la entrada.
    if req.historical:
        flash("Este expediente ya se encuentra cerrado (Histórico) y no admite más gestiones operativas.", "warning")
        return redirect(url_for('requests.state_admin_dashboard'))
        
    return render_template('requests/state_request_detail.html', req=req)
