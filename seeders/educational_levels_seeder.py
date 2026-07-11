from app.extensions import db
from app.models.educational_level_model import EducationalLevel

def seed_educational_levels():
    if EducationalLevel.query.count() > 0:
        print("Educational levels already seeded.")
        return

    levels_data = [
        {
            "level_code": "EDUL-001",
            "name": "Educación Inicial",
            "description": "Nivel que abarca la atención pedagógica a niños y niñas en edades tempranas antes de la escolaridad básica."
        },
        {
            "level_code": "EDUL-002",
            "name": "Educación Primaria",
            "description": "Nivel fundamental de la educación obligatoria que comprende la formación básica integral."
        },
        {
            "level_code": "EDUL-003",
            "name": "Educación Media General",
            "description": "Nivel que prepara a los estudiantes en conocimientos generales para su transición a la educación superior."
        },
        {
            "level_code": "EDUL-004",
            "name": "Educación Media Técnica",
            "description": "Nivel orientado a la formación profesional en áreas técnicas específicas con salida laboral."
        },
        {
            "level_code": "EDUL-005",
            "name": "Universitario / Pregrado",
            "description": "Estudios de educación superior orientados a la formación profesional en licenciaturas e ingenierías."
        },
        {
            "level_code": "EDUL-006",
            "name": "Universitario / Postgrado",
            "description": "Estudios de especialización, maestrías y doctorados posteriores a la obtención de un título universitario."
        }
    ]

    for data in levels_data:
        level = EducationalLevel(**data)
        db.session.add(level)
    
    db.session.commit()
    print("Educational levels seeded successfully.")