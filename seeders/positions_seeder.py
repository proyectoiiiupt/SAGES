from app.extensions import db
from app.models.position_model import Position

def seed_positions():
    if Position.query.count() > 0:
        print("Positions already seeded.")
        return

    positions = [
        {
            "position_code": "POS-001",
            "name": "Rector",
            "description": "Máxima autoridad ejecutiva de la institución, responsable de la dirección general, representación legal y cumplimiento de las políticas universitarias."
        },
        {
            "position_code": "POS-002",
            "name": "Vicerrector Académico",
            "description": "Responsable de coordinar, supervisar y evaluar las políticas académicas, planes de estudio, desarrollo docente y programas de formación."
        },
        {
            "position_code": "POS-003",
            "name": "Director",
            "description": "Encargado de la gestión administrativa, planificación curricular y supervisión de las actividades académicas."
        },
        {
            "position_code": "POS-004",
            "name": "Coordinador",
            "description": "Gestiona, supervisa y articula los procesos pedagógicos, administrativos y de convivencia dentro de una institución escolar."
        },
        {
            "position_code": "POS-005",
            "name": "Tutor Académico",
            "description": "Docente encargado de guiar, asesorar y evaluar el progreso formativo, pasantías o proyectos de servicio de los estudiantes e internos."
        },
        {
            "position_code": "POS-006",
            "name": "Gerente General",
            "description": "Máxima autoridad directiva de la empresa u organización, responsable de la toma de decisiones estratégicas y del cumplimiento de metas globales."
        },
        {
            "position_code": "POS-007",
            "name": "Jefe de Departamento",
            "description": "Líder de un área de conocimiento o soporte específico, encargado de coordinar al personal docente o técnico asignado."
        },
        {
            "position_code": "POS-008",
            "name": "Gerente de Operaciones",
            "description": "Encargado de supervisar la ejecución diaria de los servicios, optimizar los procesos internos y asegurar la eficiencia en la entrega de soluciones."
        },
        {
            "position_code": "POS-009",
            "name": "Líder de Proyecto",
            "description": "Responsable de coordinar al equipo de desarrollo, gestionar el backlog de requerimientos, mitigar riesgos y asegurar las entregas a tiempo."
        },
        {
            "position_code": "POS-010",
            "name": "Coordinador de Formación",
            "description": "Responsable de planificar, gestionar y hacer seguimiento a las solicitudes, cursos y formación de atención hacia las comunidades educativas."
        },
    ]

    # Inserción directa en la base de datos
    for data in positions:
        position = Position(**data)
        db.session.add(position)
    
    db.session.commit()
    print("Positions seeded successfully.")