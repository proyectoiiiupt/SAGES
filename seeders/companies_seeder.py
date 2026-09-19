from app.extensions import db
from app.models.company_model import Company

def seed_companies():
    if Company.query.count() > 0:
        print("Companies already seeded.")
        return

    company_data = {
        "company_code": "COMP-001",
        "company_name": "Corporación Eléctrica Nacional (CORPOELEC)",
        "identification_type": "G",  # Gubernamental / Estado
        "rif": "20010014-3"        # RIF institucional real de la corporación
    }

    company = Company(**company_data)
    db.session.add(company)
    
    db.session.commit()
    print("Companies seeded successfully.")