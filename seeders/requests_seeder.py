from app.extensions import db
from app.models.request_model import Request
from app.models.request_planning_model import RequestPlanning
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.training_model import Training
from app.models.status_model import Status
from datetime import datetime, timedelta, timezone

def seed_requests():
    """
    Seeder para inyectar solicitudes (Requests) de prueba asociadas
    al primer solicitante del sistema, con el fin de probar las
    vistas y paneles sin ensuciar la base de datos de producción.
    """
    if Request.query.count() > 0:
        print("Requests already seeded.")
        return

    # 1. Buscar el primer staff institucional disponible (El solicitante)
    staff = InstitutionalStaff.query.first()
    if not staff:
        print("Error: No se encontró InstitutionalStaff. Ejecuta institutional_staff_seeder primero.")
        return

    # 2. Buscar 3 formaciones para asignarles a las solicitudes
    trainings = Training.query.limit(3).all()
    if len(trainings) < 3:
        print("Error: No hay suficientes Trainings. Ejecuta trainings_seeder primero.")
        return

    # 3. Buscar los estatus requeridos (Nueva, Pendiente, Planificada)
    status_new = Status.query.filter_by(status_code='STAT-003').first()
    status_pending = Status.query.filter_by(status_code='STAT-004').first()
    status_planned = Status.query.filter_by(status_code='STAT-005').first()

    if not all([status_new, status_pending, status_planned]):
        print("Error: No se encontraron los estatus necesarios. Ejecuta status_seeder primero.")
        return

    # 4. Construir la data de prueba
    requests_data = [
        {
            "request_code": "REQ-TEST-001",
            "institutional_staff_id": staff.id,
            "training_id": trainings[0].id,
            "description": "Solicitud generada automáticamente para evaluar estado: NUEVA.",
            "status_id": status_new.id
        },
        {
            "request_code": "REQ-TEST-002",
            "institutional_staff_id": staff.id,
            "training_id": trainings[1].id,
            "description": "Solicitud generada automáticamente para evaluar estado: PENDIENTE/EN REVISIÓN.",
            "status_id": status_pending.id
        },
        {
            "request_code": "REQ-TEST-003",
            "institutional_staff_id": staff.id,
            "training_id": trainings[2].id,
            "description": "Solicitud generada automáticamente para evaluar estado: PLANIFICADA.",
            "status_id": status_planned.id
        }
    ]

    # 5. Inserción quirúrgica en la DB
    for data in requests_data:
        req = Request(**data)
        db.session.add(req)
        db.session.flush() # Hacemos flush para que PostgreSQL nos devuelva el ID recién insertado

        # Si el estatus es Planificada, inyectamos una planificación asociada
        if req.status_id == status_planned.id:
            planning = RequestPlanning(
                requests_id=req.id,
                planned_for=(datetime.now(timezone.utc) + timedelta(days=5)).date() # Fecha planificada para dentro de 5 días
            )
            db.session.add(planning)
    
    db.session.commit()
    print("Requests seeded successfully.")
