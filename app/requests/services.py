from sqlalchemy.orm import joinedload
from app.models.request_model import Request
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.user_model import User
from app.models.status_model import Status
from app.models.training_model import Training

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


def create_training_request(user_id: int, training_id: int, description: str) -> tuple[bool, str]:
    """
    Registra una nueva solicitud (Wizard US-34) de forma transaccional.
    Valida la existencia del usuario, asociación institucional y duplicidad.
    """
    from app.extensions import db
    user = User.query.get(user_id)
    
    if not user or not user.person or not user.person.institutional_staff:
        return False, "Usuario no autorizado o sin afiliación institucional."
        
    institutional_staff_id = user.person.institutional_staff[0].id
    institution_id = user.person.institutional_staff[0].institution_id
    
    # 1. Validación anti-duplicidad (Institucional)
    duplicity_check = check_request_duplicity(institution_id, training_id)
    
    if duplicity_check.get("is_duplicate"):
        return False, f"Su institución educativa ya posee una solicitud activa para este mismo tema formativo (Trámite: {duplicity_check.get('code')}). Por favor, elija un tema distinto."
        
    # 2. Buscar Estatus inicial 'Nuevo' (STAT-003)
    status_new = Status.query.filter_by(status_code='STAT-003').first()
    if not status_new:
        return False, "Error interno de sistema: Código de estado inicial no encontrado."
        
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
        return True, "Solicitud radicada de forma exitosa."
    except Exception as e:
        db.session.rollback()
        return False, "Ocurrió un error en la base de datos al registrar la solicitud."
