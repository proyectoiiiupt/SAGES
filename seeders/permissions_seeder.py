from app.extensions import db
from app.models.permission_model import Permission

def seed_permissions():
    if Permission.query.count() > 0:
        print("Permissions already seeded.")
        return

    permissions_data = [
        {"permission_code": "PERM-001", "name": "Inicio Super Admin", "view": "inicio_super_admin"},
        {"permission_code": "PERM-002", "name": "Inicio Admin Estadal", "view": "inicio_admin_estadal"},
        {"permission_code": "PERM-003", "name": "Inicio Solicitante", "view": "inicio_solicitante"},
        {"permission_code": "PERM-004", "name": "Panel Administrativo Nacional", "view": "panel_admin_nacional"},
        {"permission_code": "PERM-005", "name": "Panel Administrativo Estadal", "view": "panel_admin_estadal"},
        {"permission_code": "PERM-006", "name": "Gestión de Solicitudes Generales", "view": "gestion_solicitudes_generales"},
        {"permission_code": "PERM-007", "name": "Gestión de Solicitudes Atención", "view": "gestion_solicitudes_atencion"},
        {"permission_code": "PERM-008", "name": "Crear Solicitud", "view": "crear_solicitud"},
        {"permission_code": "PERM-009", "name": "Ver mis Solicitudes", "view": "ver_mis_solicitudes"},
        {"permission_code": "PERM-010", "name": "Ver Catalogo de Formación", "view": "ver_catalogo_formacion"},
        {"permission_code": "PERM-011", "name": "Asignar a Estados", "view": "asignar_estados"},
        {"permission_code": "PERM-012", "name": "Asignar a Niveles Educativos", "view": "asignar_niveles_educativos"},
        {"permission_code": "PERM-013", "name": "Cargar Formación", "view": "cargar_formacion"},
        {"permission_code": "PERM-014", "name": "Ver Estadísticas", "view": "ver_estadisticas"},
        {"permission_code": "PERM-015", "name": "Generar Indicadores", "view": "generar_indicadores"},
        {"permission_code": "PERM-016", "name": "Generar Reportes", "view": "generar_reportes"},
        {"permission_code": "PERM-017", "name": "Gestionar Usuarios", "view": "gestionar_usuarios"},
        {"permission_code": "PERM-018", "name": "Registrar Usuarios", "view": "registrar_usuarios"},
        {"permission_code": "PERM-019", "name": "Gestionar Institución", "view": "gestionar_institucion"},
        {"permission_code": "PERM-020", "name": "Configuración del sistema", "view": "configuracion_sistema"}
    ]

    for data in permissions_data:
        permission = Permission(**data)
        db.session.add(permission)
    
    db.session.commit()
    print("Permissions seeded successfully.")
