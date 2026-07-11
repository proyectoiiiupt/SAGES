from app.extensions import db
from app.models.training_model import Training
from app.models.training_category_model import TrainingCategory
from app.models.status_model import Status

def seed_trainings():
    if Training.query.count() > 0:
        print("Trainings already seeded.")
        return

    trainings_data = [
        {
            "training_code": "TRN-001",
            "category_code": "TCAT-001", # Taller
            "name": "Reparación de Bombillos LED y Ahorradores",
            "description": "Taller práctico para la comunidad enfocado en técnicas básicas para el diagnóstico y reparación de bombillos, fomentando el reciclaje y la autogestión.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-002",
            "category_code": "TCAT-003", # Charla
            "name": "Uso Racional y Eficiente de la Energía (Ahorro Energético)",
            "description": "Charla de concientización sobre hábitos de consumo eléctrico en el hogar para disminuir la demanda y proteger el medio ambiente.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-003",
            "category_code": "TCAT-007", # Foro
            "name": "Prevención de Riesgos Eléctricos en el Hogar",
            "description": "Foro comunitario para identificar vulnerabilidades eléctricas residenciales, prevención de cortocircuitos y medidas de seguridad familiar.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-004",
            "category_code": "TCAT-001", # Taller
            "name": "Mantenimiento Preventivo de Electrodomésticos",
            "description": "Formación práctica para el cuidado, limpieza y extensión de la vida útil de los equipos electrodomésticos de mayor consumo.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-005",
            "category_code": "TCAT-005", # Asamblea
            "name": "Conformación de Mesas Técnicas de Energía",
            "description": "Asamblea participativa para orientar a los consejos comunales en la creación y gestión de mesas técnicas de energía en sus sectores.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-006",
            "category_code": "TCAT-006", # Seminario
            "name": "Energías Alternativas y Sistemas Fotovoltaicos Básicos",
            "description": "Seminario introductorio sobre el funcionamiento de paneles solares y alternativas de respaldo energético para comunidades organizadas.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-007",
            "category_code": "TCAT-003", # Charla
            "name": "Lectura de Medidores y Comprensión del Consumo",
            "description": "Orientación para que los usuarios aprendan a leer sus medidores eléctricos y comprendan cómo se estructura su consumo mensual.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-008",
            "category_code": "TCAT-001", # Taller
            "name": "Primeros Auxilios ante Accidentes Eléctricos",
            "description": "Taller vital de primeros auxilios y protocolos de acción rápida frente a situaciones de choque eléctrico o quemaduras.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-009",
            "category_code": "TCAT-002", # Conversatorio
            "name": "Poda Preventiva y Resguardo del Tendido Eléctrico",
            "description": "Conversatorio sobre la importancia de reportar y despejar la vegetación cercana a las líneas de tensión para evitar interrupciones del servicio.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-010",
            "category_code": "TCAT-002", # Conversatorio
            "name": "Sensibilización y Resguardo del Sistema Eléctrico",
            "description": "Espacio de diálogo para fomentar el sentido de pertenencia y la denuncia comunitaria ante actos de sabotaje a la infraestructura eléctrica.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-011",
            "category_code": "TCAT-004", # Congreso
            "name": "Innovación Tecnológica en la Distribución Eléctrica",
            "description": "Congreso dirigido a estudiantes y profesionales sobre los nuevos avances y tecnologías aplicadas a la red de distribución eléctrica nacional.",
            "status_code": "STAT-001"
        }
    ]

    for data in trainings_data:
        category_code = data.pop("category_code")
        status_code = data.pop("status_code")

        category = TrainingCategory.query.filter_by(category_code=category_code).first()
        status = Status.query.filter_by(status_code=status_code).first()

        if not category:
            print(f"Error: Categoría '{category_code}' no encontrada. Ejecuta seed_training_categories primero.")
            return
        if not status:
            print(f"Error: Estatus '{status_code}' no encontrado. Ejecuta seed_status primero.")
            return

        data["training_category_id"] = category.id
        data["status_id"] = status.id

        training = Training(**data)
        db.session.add(training)
    
    db.session.commit()
    print("Trainings seeded successfully.")