from app.extensions import db
from app.models.permission_role_model import PermissionRole
from app.models.role_model import Role
from app.models.permission_model import Permission

def seed_permission_roles():
    if PermissionRole.query.count() > 0:
        print("Permission roles already seeded.")
        return

    mappings = [
        # --- SUPER ADMIN (ROL-001) ---
        {"role_code": "ROL-001", "permission_code": "PERM-001"}, # Ver Inicio
        {"role_code": "ROL-001", "permission_code": "PERM-002"}, # Ver Panel Administrativo
        {"role_code": "ROL-001", "permission_code": "PERM-003"}, # Gestión de Solicitudes
        {"role_code": "ROL-001", "permission_code": "PERM-005"}, # Ver Catalogo de Formación
        {"role_code": "ROL-001", "permission_code": "PERM-006"}, # Asignar a Estados
        {"role_code": "ROL-001", "permission_code": "PERM-007"}, # Asignar a Niveles Educativos
        {"role_code": "ROL-001", "permission_code": "PERM-008"}, # Cargar Formación
        {"role_code": "ROL-001", "permission_code": "PERM-009"}, # Ver Estadísticas
        {"role_code": "ROL-001", "permission_code": "PERM-010"}, # Gestionar Usuarios
        {"role_code": "ROL-001", "permission_code": "PERM-011"}, # Registrar Usuarios
        {"role_code": "ROL-001", "permission_code": "PERM-012"}, # Gestionar Institución
        {"role_code": "ROL-001", "permission_code": "PERM-013"}, # Configuración del sistema

        # --- ADMIN ESTADAL (ROL-002) ---
        {"role_code": "ROL-002", "permission_code": "PERM-001"}, # Ver Inicio
        {"role_code": "ROL-002", "permission_code": "PERM-002"}, # Ver Panel Administrativo
        {"role_code": "ROL-002", "permission_code": "PERM-003"}, # Gestión de Solicitudes
        {"role_code": "ROL-002", "permission_code": "PERM-005"}, # Ver Catalogo de Formación
        {"role_code": "ROL-002", "permission_code": "PERM-006"}, # Asignar a Estados
        {"role_code": "ROL-002", "permission_code": "PERM-009"}, # Ver Estadísticas
        {"role_code": "ROL-002", "permission_code": "PERM-010"}, # Gestionar Usuarios
        {"role_code": "ROL-002", "permission_code": "PERM-012"}, # Gestionar Institución

        # --- SOLICITANTE (ROL-003) ---
        {"role_code": "ROL-003", "permission_code": "PERM-001"}, # Ver Inicio
        {"role_code": "ROL-003", "permission_code": "PERM-004"}, # Crear Solicitud
        {"role_code": "ROL-003", "permission_code": "PERM-005"}  # Ver Catalogo de Formación
    ]

    for data in mappings:
        role_code = data.pop("role_code")
        permission_code = data.pop("permission_code")

        role = Role.query.filter_by(role_code=role_code).first()
        permission = Permission.query.filter_by(permission_code=permission_code).first()

        if not role:
            print(f"Error: Rol '{role_code}' no encontrado. Ejecuta seed_roles primero.")
            return
        if not permission:
            print(f"Error: Permiso '{permission_code}' no encontrado. Ejecuta seed_permissions primero.")
            return

        data["role_id"] = role.id
        data["permission_id"] = permission.id

        permission_role = PermissionRole(**data)
        db.session.add(permission_role)
    
    db.session.commit()
    print("Permission roles seeded successfully.")
