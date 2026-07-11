from app.extensions import db
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.person_model import Person
from app.models.institution_model import Institution
from app.models.position_model import Position

def seed_institutional_staff():
    if InstitutionalStaff.query.count() > 0:
        print("Institutional staff already seeded.")
        return

    staff_data = [
        {
            "person_code": "PERS-003", 
            "institution_code": "EDU-001", # UCV (Universidad)
            "position_code": "POS-001"     # Rector
        },
        {
            "person_code": "PERS-004", 
            "institution_code": "EDU-002", # UCAB (Universidad)
            "position_code": "POS-002"     # Vicerrector Académico
        },
        {
            "person_code": "PERS-005", 
            "institution_code": "EDU-003", # Liceo de Aplicación
            "position_code": "POS-003"     # Director
        },
        {
            "person_code": "PERS-006", 
            "institution_code": "EDU-004", # Colegio La Salle (Complejo Integral)
            "position_code": "POS-004"     # Coordinador
        },
        {
            "person_code": "PERS-007", 
            "institution_code": "EDU-005", # E.T.I. José de San Martín
            "position_code": "POS-007"     # Jefe de Departamento
        },
        {
            "person_code": "PERS-008", 
            "institution_code": "EDU-006", # Fe y Alegría La Rinconada
            "position_code": "POS-005"     # Tutor Académico
        },
        {
            "person_code": "PERS-009", 
            "institution_code": "EDU-007", # U.E. Municipal Andrés Eloy Blanco
            "position_code": "POS-004"     # Coordinador
        },
        {
            "person_code": "PERS-010", 
            "institution_code": "EDU-008", # IUT Antonio José de Sucre
            "position_code": "POS-010"     # Coordinador de Formación
        },
        {
            "person_code": "PERS-011", 
            "institution_code": "EDU-009", # Centro San Juan Bosco
            "position_code": "POS-003"     # Director
        }
    ]

    for data in staff_data:
        person_code = data.pop("person_code")
        institution_code = data.pop("institution_code")
        position_code = data.pop("position_code")

        person = Person.query.filter_by(person_code=person_code).first()
        institution = Institution.query.filter_by(institution_code=institution_code).first()
        position = Position.query.filter_by(position_code=position_code).first()

        if not person:
            print(f"Error: Persona con código '{person_code}' no encontrada. Ejecuta seed_persons primero.")
            return
        if not institution:
            print(f"Error: Institución con código '{institution_code}' no encontrada. Ejecuta seed_institutions primero.")
            return
        if not position:
            print(f"Error: Cargo con código '{position_code}' no encontrado. Ejecuta seed_positions primero.")
            return

        data["person_id"] = person.id
        data["institution_id"] = institution.id
        data["position_id"] = position.id

        staff = InstitutionalStaff(**data)
        db.session.add(staff)
    
    db.session.commit()
    print("Institutional staff seeded successfully.")