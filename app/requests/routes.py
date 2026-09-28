from flask import render_template
from flask_login import login_required, current_user
from app.decorators.auth_decorators import role_required, check_permissions
from app.requests import requests_bp
from app.requests.services import get_applicant_active_requests
from app.models.user_model import User

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
