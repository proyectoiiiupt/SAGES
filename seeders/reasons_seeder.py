from app.extensions import db
from app.models.reason_model import Reason

def seed_reasons():
    if Reason.query.count() > 0:
        print("Reasons already seeded.")
        return

    reasons_data = [
        {
            "reason_code": "REAS-001",
            "name": "Dificultades logísticas / Transporte",
            "description": "Inconvenientes relacionados con el traslado del personal o la movilización de insumos necesarios para la actividad."
        },
        {
            "reason_code": "REAS-002",
            "name": "Cruce con actividades institucionales superiores",
            "description": "La fecha de la actividad coincide con eventos de mayor jerarquía o cronogramas institucionales inamovibles."
        },
        {
            "reason_code": "REAS-003",
            "name": "Suspensión de actividad en el plantel",
            "description": "Cierre temporal o suspensión de actividades académicas/administrativas por causas de fuerza mayor o calendario escolar."
        },
        {
            "reason_code": "REAS-004",
            "name": "Falta de disponibilidad del ponente/facilitador",
            "description": "El personal encargado de impartir la formación no se encuentra disponible en la fecha programada."
        },
        {
            "reason_code": "REAS-005",
            "name": "Fallas de infraestructura / Servicios básicos",
            "description": "Problemas con el suministro eléctrico, agua, conectividad a internet o daños en la planta física del plantel."
        },
        {
            "reason_code": "REAS-006",
            "name": "Baja participación o convocatoria insuficiente",
            "description": "El número de asistentes registrados o presentes es menor al requerido para garantizar el éxito de la actividad."
        },
        {
            "reason_code": "REAS-007",
            "name": "Otro",
            "description": "Motivo no especificado en las categorías anteriores que requiere observación adicional por parte del usuario."
        }
    ]

    for data in reasons_data:
        reason = Reason(**data)
        db.session.add(reason)
    
    db.session.commit()
    print("Reasons seeded successfully.")