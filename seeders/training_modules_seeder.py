from app.extensions import db
from app.models.training_module_model import TrainingModule

OFFICIAL_MODULES = [
    {
        "module_code": "MOD-001",
        "name": "Uso Racional y Eficiente de la Energía (UREE)",
        "description": "Fundamentos de concienciación y optimización energética en el ámbito residencial y educativo.",
        "order_index": 1
    },
    {
        "module_code": "MOD-002",
        "name": "Sustitución Tecnológica",
        "description": "Procesos de recambio y modernización hacia luminarias y equipos de alta eficiencia energética.",
        "order_index": 2
    },
    {
        "module_code": "MOD-003",
        "name": "Eficiencia Energética Institucional y Productiva",
        "description": "Buenas prácticas, diagnósticos y auditorías en entes del sector público e industrial.",
        "order_index": 3
    },
    {
        "module_code": "MOD-004",
        "name": "Fuentes Alternativas",
        "description": "Aprovechamiento de energías renovables, solar fotovoltaica, eólica y tecnologías limpias.",
        "order_index": 4
    }
]

def seed_training_modules():
    for mod_data in OFFICIAL_MODULES:
        exists = TrainingModule.query.filter_by(module_code=mod_data["module_code"]).first()
        if not exists:
            module = TrainingModule(**mod_data)
            db.session.add(module)
    db.session.commit()
    print("Training modules seeded successfully.")
