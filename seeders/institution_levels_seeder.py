from app.extensions import db
from app.models.institution_level_model import InstitutionLevel
from app.models.institution_model import Institution
from app.models.educational_level_model import EducationalLevel

def seed_institution_levels():
    if InstitutionLevel.query.count() > 0:
        print("Institution levels associations already seeded.")
        return

    associations = [
        {"institution_code": "EDU-001", "level_code": "EDUL-005"}, # UCV - Universitario Pregrado
        {"institution_code": "EDU-001", "level_code": "EDUL-006"}, # UCV - Universitario Postgrado
        {"institution_code": "EDU-002", "level_code": "EDUL-005"}, # UCAB - Universitario Pregrado
        {"institution_code": "EDU-002", "level_code": "EDUL-006"}, # UCAB - Universitario Postgrado
        {"institution_code": "EDU-003", "level_code": "EDUL-003"}, 
        {"institution_code": "EDU-004", "level_code": "EDUL-001"}, 
        {"institution_code": "EDU-004", "level_code": "EDUL-002"}, 
        {"institution_code": "EDU-005", "level_code": "EDUL-003"},
        {"institution_code": "EDU-006", "level_code": "EDUL-002"},
        {"institution_code": "EDU-006", "level_code": "EDUL-003"},
        {"institution_code": "EDU-007", "level_code": "EDUL-002"},
        {"institution_code": "EDU-008", "level_code": "EDUL-005"},
        {"institution_code": "EDU-009", "level_code": "EDUL-005"},
        {"institution_code": "EDU-010", "level_code": "EDUL-002"},
        {"institution_code": "EDU-011", "level_code": "EDUL-004"},
    ]

    for data in associations:
        institution = Institution.query.filter_by(institution_code=data["institution_code"]).first()
        educational_level = EducationalLevel.query.filter_by(level_code=data["level_code"]).first()

        if not institution:
            print(f"Error: Institución '{data['institution_code']}' no encontrada.")
            continue
        if not educational_level:
            print(f"Error: Nivel educativo '{data['level_code']}' no encontrado.")
            continue

        assoc = InstitutionLevel(
            institution_id=institution.id,
            educational_level_id=educational_level.id
        )
        db.session.add(assoc)
    
    db.session.commit()
    print("Institution levels associations seeded successfully.")