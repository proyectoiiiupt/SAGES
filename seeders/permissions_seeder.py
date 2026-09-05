from app.extensions import db
from app.models.permission_model import Permission

def seed_permissions():
    if Permission.query.count() > 0:
        print("Permissions already seeded.")
        return

    permissions_data = [
        {"permission_code": "PERM-001", "name": "Ver Inicio", "view": "view_home"},
        {"permission_code": "PERM-002", "name": "Ver Panel Administrativo", "view": "view_admin_panel"},
        {"permission_code": "PERM-003", "name": "Gestión de Solicitudes", "view": "manage_requests"},
        {"permission_code": "PERM-004", "name": "Crear Solicitud", "view": "create_request"},
        {"permission_code": "PERM-005", "name": "Ver Catalogo de Formación", "view": "view_training_catalog"},
        {"permission_code": "PERM-006", "name": "Asignar a Estados", "view": "assign_to_states"},
        {"permission_code": "PERM-007", "name": "Asignar a Niveles Educativos", "view": "assign_to_educational_levels"},
        {"permission_code": "PERM-008", "name": "Cargar Formación", "view": "upload_training"},
        {"permission_code": "PERM-009", "name": "Ver Estadísticas", "view": "view_statistics"},
        {"permission_code": "PERM-010", "name": "Gestionar Usuarios", "view": "manage_users"},
        {"permission_code": "PERM-011", "name": "Registrar Usuarios", "view": "register_users"},
        {"permission_code": "PERM-012", "name": "Gestionar Institución", "view": "manage_institution"},
        {"permission_code": "PERM-013", "name": "Configuración del sistema", "view": "system_configuration"},
        {"permission_code": "PERM-014", "name": "Ver Mi Institución", "view": "view_my_institution"}
    ]

    for data in permissions_data:
        permission = Permission(**data)
        db.session.add(permission)
    
    db.session.commit()
    print("Permissions seeded successfully.")
