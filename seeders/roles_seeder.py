from app.extensions import db
from app.models.role_model import Role

def seed_roles():
    if Role.query.count() > 0:
        print("Roles already seeded.")
        return

    roles = [
        {"role_code": "ROL-001", "name": "super_admin", "description": "Administrador del sistema con acceso total"},
        {"role_code": "ROL-002", "name": "state_admin", "description": "Administrador a nivel estadal"},
        {"role_code": "ROL-003", "name": "applicant", "description": "Usuario solicitante"}
    ]

    for data in roles:
        role = Role(**data)
        db.session.add(role)
    
    db.session.commit()
    print("Roles seeded successfully.")
