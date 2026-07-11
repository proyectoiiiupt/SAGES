from app.extensions import db
from app.models.place_model import Place
from app.models.company_model import Company
from app.models.parish_model import Parish
from app.models.status_model import Status

def seed_places():
    if Place.query.count() > 0:
        print("Places already seeded.")
        return

    places_data = [
        {
            "place_code": "PLC-001",
            "company_code": "COMP-001",  # CORPOELEC
            "name": "Sede Principal - Centro Empresarial Caracas",
            "parish_code": "PAR-1131",   # San Bernardino (Verificado en tu parroquias seeder)
            "address": "Av. Vollmer entre Caracas y Alameda, Edificio Centro Empresarial Caracas, San Bernardino, Caracas.",
            "phone": "0212-5021111",
            "status_code": "STAT-001"    # Activo
        },
        {
            "place_code": "PLC-002",
            "company_code": "COMP-001",  # CORPOELEC
            "name": "Centro de Servicio Técnico - Catia",
            "parish_code": "PAR-1137",   # Sucre (Catia) (Verificado en tu parroquias seeder)
            "address": "Av. Principal de Catia, Complejo Operativo e Industrial, Catia, Caracas.",
            "phone": "0212-8602233",
            "status_code": "STAT-001"    # Activo
        }
    ]

    for data in places_data:
        company_code = data.pop("company_code")
        parish_code = data.pop("parish_code")
        status_code = data.pop("status_code")

        company = Company.query.filter_by(company_code=company_code).first()
        parish = Parish.query.filter_by(parish_code=parish_code).first()
        status = Status.query.filter_by(status_code=status_code).first()

        if not company:
            print(f"Error: Empresa con código '{company_code}' no encontrada. Ejecuta seed_companies primero.")
            return
        if not parish:
            print(f"Error: Parroquia con código '{parish_code}' no encontrada. Revisa tu parishes_seeder.")
            return
        if not status:
            print(f"Error: Estado con código '{status_code}' no encontrado. Ejecuta seed_status primero.")
            return

        data["company_id"] = company.id
        data["parish_id"] = parish.id
        data["status_id"] = status.id

        place = Place(**data)
        db.session.add(place)

    db.session.commit()
    print("Places seeded successfully.")