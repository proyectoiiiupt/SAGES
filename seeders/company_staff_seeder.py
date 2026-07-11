from app.extensions import db
from app.models.company_staff_model import CompanyStaff
from app.models.person_model import Person
from app.models.place_model import Place
from app.models.position_model import Position

def seed_company_staff():
    if CompanyStaff.query.count() > 0:
        print("Company staff already seeded.")
        return

    staff_data = [
        {
            "person_code": "PERS-001",
            "place_code": "PLC-001",   # Sede Principal
            "position_code": "POS-006" # Gerente General
        },
        {
            "person_code": "PERS-002",
            "place_code": "PLC-001",   # Sede Principal
            "position_code": "POS-008" # Gerente de Operaciones
        }
    ]

    for data in staff_data:
        person_code = data.pop("person_code")
        place_code = data.pop("place_code")
        position_code = data.pop("position_code")

        person = Person.query.filter_by(person_code=person_code).first()
        place = Place.query.filter_by(place_code=place_code).first()
        position = Position.query.filter_by(position_code=position_code).first()

        if not person:
            print(f"Error: Persona con código '{person_code}' no encontrada. Ejecuta seed_persons primero.")
            return
        if not place:
            print(f"Error: Sede con código '{place_code}' no encontrada. Ejecuta tu seeder de places primero.")
            return
        if not position:
            print(f"Error: Cargo con código '{position_code}' no encontrado. Ejecuta seed_positions primero.")
            return

        data["person_id"] = person.id
        data["place_id"] = place.id
        data["position_id"] = position.id

        staff = CompanyStaff(**data)
        db.session.add(staff)
    
    db.session.commit()
    print("Company staff seeded successfully.")