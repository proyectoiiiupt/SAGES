from app.extensions import db
from app.models.institution_type_model import InstitutionType

def seed_institution_types():
    if InstitutionType.query.count() > 0:
        print("Institution types already seeded.")
        return

    institution_types = [
        {
            "institution_type_code": "INST-001",
            "name": "Universidad",
            "description": "Instituciones de educación superior destinadas a la formación profesional, investigación, especializaciones y estudios de pregrado y postgrado."
        },
        {
            "institution_type_code": "INST-002",
            "name": "Instituto Universitario",
            "description": "Centros educativos de nivel superior enfocados principalmente en carreras técnicas cortas, ideales para la formación de Técnicos Superiores Universitarios (TSU) e ingenierías aplicadas."
        },
        {
            "institution_type_code": "INST-003",
            "name": "Liceo / Educación Media",
            "description": "Instituciones encargadas de la educación media general y técnica, orientadas a jóvenes que cursan desde el primer año hasta el año de graduación de bachillerato."
        },
        {
            "institution_type_code": "INST-004",
            "name": "Escuela Básica / Primaria",
            "description": "Centros educativos dedicados a la enseñanza fundamental obligatoria, abarcando las etapas de educación inicial y primaria."
        },
        {
            "institution_type_code": "INST-005",
            "name": "Centro de Formación Técnica y Laboral",
            "description": "Espacios orientados a la capacitación de oficios, cursos técnicos, adiestramiento profesional continuo y formación comunitaria para el trabajo."
        },
        {
            "institution_type_code": "INST-006",
            "name": "Complejo Educativo Integral",
            "description": "Unidades o planteles que unifican múltiples niveles del sistema educativo en una sola estructura organizativa (desde inicial hasta bachillerato)."
        }
    ]

    for data in institution_types:
        inst_type = InstitutionType(**data)
        db.session.add(inst_type)
    
    db.session.commit()
    print("Institution types seeded successfully.")