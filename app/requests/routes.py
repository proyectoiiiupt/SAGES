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

