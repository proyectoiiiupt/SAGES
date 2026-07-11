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
        {"role_code": "ROL-001", "permission_code": "PERM-001"}, # Inicio Super Admin
        {"role_code": "ROL-001", "permission_code": "PERM-004"}, # Panel Administrativo Nacional
        {"role_code": "ROL-001", "permission_code": "PERM-006"}, # Gestión de Solicitudes Generales
        {"role_code": "ROL-001", "permission_code": "PERM-010"}, # Ver Catalogo de Formación
        {"role_code": "ROL-001", "permission_code": "PERM-011"}, # Asignar a Estados
        {"role_code": "ROL-001", "permission_code": "PERM-012"}, # Asignar a Niveles Educativos
        {"role_code": "ROL-001", "permission_code": "PERM-013"}, # Cargar Formación
        {"role_code": "ROL-001", "permission_code": "PERM-014"}, # Ver Estadísticas
        {"role_code": "ROL-001", "permission_code": "PERM-015"}, # Generar Indicadores
        {"role_code": "ROL-001", "permission_code": "PERM-016"}, # Generar Reportes
        {"role_code": "ROL-001", "permission_code": "PERM-017"}, # Gestionar Usuarios
        {"role_code": "ROL-001", "permission_code": "PERM-018"}, # Registrar Usuarios
        {"role_code": "ROL-001", "permission_code": "PERM-019"}, # Gestionar Institución
        {"role_code": "ROL-001", "permission_code": "PERM-020"}, # Configuración del sistema

        # --- ADMIN ESTADAL (ROL-002) ---
        {"role_code": "ROL-002", "permission_code": "PERM-002"}, # Inicio Admin Estadal
        {"role_code": "ROL-002", "permission_code": "PERM-005"}, # Panel Administrativo Estadal
        {"role_code": "ROL-002", "permission_code": "PERM-007"}, # Gestión de Solicitudes Atención
        {"role_code": "ROL-002", "permission_code": "PERM-010"}, # Ver Catalogo de Formación
        {"role_code": "ROL-002", "permission_code": "PERM-011"}, # Asignar a Estados
        {"role_code": "ROL-002", "permission_code": "PERM-014"}, # Ver Estadísticas
        {"role_code": "ROL-002", "permission_code": "PERM-015"}, # Generar Indicadores
        {"role_code": "ROL-002", "permission_code": "PERM-016"}, # Generar Reportes
        {"role_code": "ROL-002", "permission_code": "PERM-017"}, # Gestionar Usuarios
        {"role_code": "ROL-002", "permission_code": "PERM-019"}, # Gestionar Institución

        # --- SOLICITANTE (ROL-003) ---
        {"role_code": "ROL-003", "permission_code": "PERM-003"}, # Inicio Solicitante
        {"role_code": "ROL-003", "permission_code": "PERM-008"}, # Crear Solicitud
        {"role_code": "ROL-003", "permission_code": "PERM-009"}, # Ver mis Solicitudes
        {"role_code": "ROL-003", "permission_code": "PERM-010"}  # Ver Catalogo de Formación
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
