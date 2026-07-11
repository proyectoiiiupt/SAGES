from app.extensions import db
from werkzeug.security import generate_password_hash
from app.models.user_model import User
from app.models.person_model import Person
from app.models.status_model import Status

def seed_users():
    if User.query.count() > 0:
        print("Users already seeded.")
        return

    users_data = [
        {"user_code": "USR-001", "person_code": "PERS-001", "status_code": "STAT-001"},
        {"user_code": "USR-002", "person_code": "PERS-002", "status_code": "STAT-001"},
        {"user_code": "USR-003", "person_code": "PERS-003", "status_code": "STAT-001"},
        {"user_code": "USR-004", "person_code": "PERS-004", "status_code": "STAT-001"},
        {"user_code": "USR-005", "person_code": "PERS-005", "status_code": "STAT-001"},
        {"user_code": "USR-006", "person_code": "PERS-006", "status_code": "STAT-001"},
        {"user_code": "USR-007", "person_code": "PERS-007", "status_code": "STAT-001"},
        {"user_code": "USR-008", "person_code": "PERS-008", "status_code": "STAT-001"},
        {"user_code": "USR-009", "person_code": "PERS-009", "status_code": "STAT-001"},
        {"user_code": "USR-010", "person_code": "PERS-010", "status_code": "STAT-001"},
        {"user_code": "USR-011", "person_code": "PERS-011", "status_code": "STAT-001"},
    ]

    for data in users_data:
        person_code = data.pop("person_code")
        status_code = data.pop("status_code")

        person = Person.query.filter_by(person_code=person_code).first()
        status = Status.query.filter_by(status_code=status_code).first()

        if not person:
            print(f"Error: No se encontró Person con código '{person_code}'. Ejecuta seed_persons primero.")
            return
        if not status:
            print(f"Error: No se encontró Status con código '{status_code}'. Ejecuta seed_status primero.")
            return

        data["person_id"] = person.id
        data["user_name"] = person.identification_number
        data["password"] = generate_password_hash(f"{person.first_name}123".lower())
        data["status_id"] = status.id
        
        user = User(**data)
        db.session.add(user)
    
    db.session.commit()
    print("Users seeded successfully.")