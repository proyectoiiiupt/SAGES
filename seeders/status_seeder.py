from app.extensions import db
from app.models.status_model import Status

def seed_status():
    if Status.query.count() > 0:
        print("Status already seeded.")
        return

    statuses = [
        {
            "status_code": "STAT-001", 
            "status_name": "Activo", 
            "description": "Se encuentra operativo y habilitado en el sistema.", 
            "context": "Usuarios y Formación"
        },
        {
            "status_code": "STAT-002", 
            "status_name": "Inactivo", 
            "description": "Ha sido deshabilitado temporal o permanentemente.", 
            "context": "Usuarios y Formación"
        },
        {
            "status_code": "STAT-003", 
            "status_name": "Nuevo", 
            "description": "La solicitud ha sido recién registrada en el sistema y espera su primera revisión.", 
            "context": "Solicitudes y Atención"
        },
        {
            "status_code": "STAT-004", 
            "status_name": "Pendiente", 
            "description": "La solicitud ha sido revisada preliminarmente, pero está en cola a la espera de asignación o acciones adicionales.", 
            "context": "Solicitudes y Atención"
        },
        {
            "status_code": "STAT-005", 
            "status_name": "Planificada", 
            "description": "La atención de la solicitud o la actividad de formación ha sido aprobada y agendada con fecha y responsable.", 
            "context": "Solicitudes y Formación"
        },
        {
            "status_code": "STAT-006", 
            "status_name": "En proceso", 
            "description": "La solicitud o formación está siendo ejecutado actualmente por el equipo asignado.", 
            "context": "Solicitudes y Atención"
        },
        {
            "status_code": "STAT-007", 
            "status_name": "Completado", 
            "description": "El formación, atención o solicitud ha sido ejecutado y finalizado de manera exitosa.", 
            "context": "Solicitudes y Atención"
        },
        {
            "status_code": "STAT-008", 
            "status_name": "Rechazado", 
            "description": "La solicitud fue denegada tras su revisión por no cumplir con los requisitos estipulados.", 
            "context": "Solicitudes y Atención"
        },
        {
            "status_code": "STAT-009", 
            "status_name": "Cancelado", 
            "description": "La solicitud fue anulada por el usuario o el administrador antes de su culminación.", 
            "context": "Solicitudes y Atención"
        }
    ]

    for data in statuses:
        status = Status(**data)
        db.session.add(status)
    
    db.session.commit()
    print("Status seeded successfully.")
