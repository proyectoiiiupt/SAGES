from app.extensions import db
from app.models.training_model import Training
from app.models.training_module_model import TrainingModule
from app.models.status_model import Status

def seed_trainings():
    if Training.query.count() > 0:
        print("Trainings already seeded.")
        return

    trainings_data = [
        # MOD-001: Uso Racional y Eficiente de la Energía (UREE)
        {
            "training_code": "TRN-001",
            "module_code": "MOD-001",
            "name": "El Sistema Eléctrico Nacional (SEN)",
            "description": "Estructura básica (Generación, Transmisión, Distribución y Comercialización) y la importancia de su preservación.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-002",
            "module_code": "MOD-001",
            "name": "Cultura del Ahorro Energético: Hábitos de Consumo en el Hogar y la Oficina",
            "description": "Buenas prácticas para el uso de equipos de alto consumo (aires acondicionados, refrigeración e iluminación).",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-003",
            "module_code": "MOD-001",
            "name": "Vampiros Energéticos",
            "description": "Identificación y control del consumo en espera (standby) de los electrodomésticos y cargadores conectados que no se están usando. *Brigadas Escolares e Integrales de Energía: Capacitación para la conformación de grupos comunitarios y estudiantiles que promuevan el uso eficiente.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-004",
            "module_code": "MOD-001",
            "name": "El Cambio Climático, Fenómeno Climatológico el Niño y la Niña, Calentamiento Global",
            "description": "La relación directa entre el derroche de energía, las emisiones de gases de efecto invernadero y los fenómenos climáticos locales.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-005",
            "module_code": "MOD-001",
            "name": "Efemérides Ambientales como Motor de Cambio",
            "description": "Aprovechamiento de fechas clave (como el Día Mundial del Ahorro de Energía) para lanzar campañas de alto impacto visual y comunitario.",
            "status_code": "STAT-001"
        },
        
        # MOD-002: Sustitución Tecnológica
        {
            "training_code": "TRN-006",
            "module_code": "MOD-002",
            "name": "Evolución de la Tecnología de Iluminación",
            "description": "Comparativa técnica entre la iluminación incandescente/fluorescente y la tecnología LED (eficiencia, lúmenes por vatio, vida útil).",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-007",
            "module_code": "MOD-002",
            "name": "Protocolos de Sustitución Tecnológica masiva",
            "description": "Metodología para el despliegue de planes de iluminación (ej. Plan José Gregorio Hernández) en centros de salud, educación y comunidades.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-008",
            "module_code": "MOD-002",
            "name": "Diagnóstico y Diagnósticos Energéticos Rápidos",
            "description": "Cómo evaluar los sistemas de iluminación existentes y calcular el potencial de ahorro antes y después de la sustitución.",
            "status_code": "STAT-001"
        },
        
        # MOD-003: Eficiencia Energética Institucional y productiva
        {
            "training_code": "TRN-009",
            "module_code": "MOD-003",
            "name": "Etiquetado de Eficiencia Energética",
            "description": "Lectura e interpretación de las etiquetas de rendimiento en electrodomésticos y equipos industriales.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-010",
            "module_code": "MOD-003",
            "name": "Optimización de Sistemas de Climatización",
            "description": "Buenas prácticas para el uso, mantenimiento y regulación de aires acondicionados en oficinas y centros asistenciales (regulación de temperaturas óptimas).",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-011",
            "module_code": "MOD-003",
            "name": "Marco Legal del Uso Racional",
            "description": "Socialización de la Ley Orgánica del Sistema y Servicio Eléctrico (LOSSE) y la Ley de Uso Racional y Eficiente de la Energía.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-012",
            "module_code": "MOD-003",
            "name": "Mantenimiento Preventivo como Factor de Ahorro",
            "description": "Mantenimiento Preventivo como Factor de Ahorro",
            "status_code": "STAT-001"
        },
        
        # MOD-004: Fuentes Alternativas
        {
            "training_code": "TRN-013",
            "module_code": "MOD-004",
            "name": "Energía Solar Fotovoltaica",
            "description": "Fundamentos de la Energía Solar Fotovoltaica: Cómo funcionan los paneles solares, medición de voltaje, y su aplicación en zonas aisladas o instituciones públicas.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-014",
            "module_code": "MOD-004",
            "name": "Protocolos de Almacenamiento y Mantenimiento Solar",
            "description": "Criterios técnicos para el traslado, limpieza, medición de voltaje y resguardo seguro de componentes fotovoltaicos.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-015",
            "module_code": "MOD-004",
            "name": "Mantenimiento y Almacenamiento de Sistemas Solares",
            "description": "Protocolos críticos para el traslado, limpieza, revisión técnica y almacenamiento seguro de paneles y bancos de baterías para prolongar su vida útil.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-016",
            "module_code": "MOD-004",
            "name": "Energía Eólica y Otras Alternativas",
            "description": "Potencial de la energía del viento, la biomasa o la micro-hidroeléctrica según las condiciones geográficas de la región.",
            "status_code": "STAT-001"
        },
        {
            "training_code": "TRN-017",
            "module_code": "MOD-004",
            "name": "Sistemas Híbridos",
            "description": "Combinación de la red eléctrica convencional con fuentes alternas para garantizar la continuidad del servicio en sectores priorizados (como centros de salud).",
            "status_code": "STAT-001"
        }
    ]

    for data in trainings_data:
        module_code = data.pop("module_code")
        status_code = data.pop("status_code")

        module = TrainingModule.query.filter_by(module_code=module_code).first()
        status = Status.query.filter_by(status_code=status_code).first()

        if not module:
            print(f"Error: Módulo '{module_code}' no encontrado. Ejecuta seed_training_modules primero.")
            return
        if not status:
            print(f"Error: Estatus '{status_code}' no encontrado. Ejecuta seed_status primero.")
            return

        data["training_module_id"] = module.id
        data["status_id"] = status.id

        training = Training(**data)
        db.session.add(training)
    
    db.session.commit()
    print("Trainings seeded successfully.")