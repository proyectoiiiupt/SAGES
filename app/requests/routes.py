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
    success, message = create_training_request(
        user_id=current_user.id,
        training_id=form.training_id.data,
        description=form.description.data
    )
    
    if success:
        return jsonify({'success': True, 'message': message}), 201
    else:
        return jsonify({'success': False, 'message': message}), 400
