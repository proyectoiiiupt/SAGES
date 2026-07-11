from app.extensions import db
from app.models.role_user_model import RoleUser
from app.models.user_model import User
from app.models.role_model import Role

def seed_role_users():
    if RoleUser.query.count() > 0:
        print("Role users already seeded.")
        return

    role_users_data = [
        {"user_code": "USR-001", "role_code": "ROL-001"},  # super_admin
        {"user_code": "USR-002", "role_code": "ROL-002"},  # state_admin
        {"user_code": "USR-003", "role_code": "ROL-003"},  
        {"user_code": "USR-004", "role_code": "ROL-003"},
        {"user_code": "USR-005", "role_code": "ROL-003"},
        {"user_code": "USR-006", "role_code": "ROL-003"},
        {"user_code": "USR-007", "role_code": "ROL-003"},
        {"user_code": "USR-008", "role_code": "ROL-003"},
        {"user_code": "USR-009", "role_code": "ROL-003"},
        {"user_code": "USR-010", "role_code": "ROL-003"},
        {"user_code": "USR-011", "role_code": "ROL-003"},
    ]

    for data in role_users_data:
        u_code = data["user_code"]
        r_code = data["role_code"]

        user = User.query.filter_by(user_code=u_code).first()
        role = Role.query.filter_by(role_code=r_code).first()

        if not user:
            print(f"Error: Usuario con código '{u_code}' no encontrado. Asegúrate de ejecutar primero el seeder de usuarios.")
            return
        if not role:
            print(f"Error: Rol con código '{r_code}' no encontrado. Asegúrate de ejecutar primero el seeder de roles.")
            return

        role_user = RoleUser(
            user_id=user.id,
            role_id=role.id
        )
        db.session.add(role_user)

    db.session.commit()
    print("Role users seeded successfully.")
