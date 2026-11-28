from functools import wraps
from flask import request, abort, jsonify, flash, redirect, url_for, current_app
from flask_login import current_user
from app.models.permission_model import Permission

def check_permissions(*view_names):
    """
    Decorador para validar si el rol del usuario en sesión tiene
    permisos sobre la vista (o alguna de las vistas) solicitadas.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return abort(401)
                
            # Usar view_names si se proporcionan, sino usar el endpoint actual (ej: 'auth.login')
            endpoints = [v for v in view_names if v] or [request.endpoint]
            
            permissions = Permission.query.filter(Permission.view.in_(endpoints)).all()
            
            if not permissions:
                import logging
                logging.warning(f"Permiso no configurado para endpoint '{endpoints}', user_id={current_user.id}")
                # Si la ruta no está registrada como un permiso en BD, denegamos el acceso
                abort(403, description="No tienes permisos para acceder a esta ruta.")
                
            allowed_perm_ids = {p.id for p in permissions}
            has_permission = False
            # Buscar si alguno de los roles del usuario tiene alguno de los permisos requeridos
            for role_assoc in current_user.roles_assoc:
                for perm_assoc in role_assoc.role.permissions_assoc:
                    if perm_assoc.permission_id in allowed_perm_ids:
                        has_permission = True
                        break
                if has_permission:
                    break
                    
            if not has_permission:
                if request.is_json or (request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html):
                    return jsonify({"error": "No tienes permisos para acceder a esta ruta."}), 403
                abort(403, description="No tienes permisos para acceder a esta ruta.")
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def role_required(*role_names):
    """
    Decorador para restringir el acceso a rutas según roles específicos.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return abort(401)
                
            has_role = False
            for role_assoc in current_user.roles_assoc:
                if role_assoc.role.name in role_names:
                    has_role = True
                    break
                    
            if not has_role:
                if request.is_json or (request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html):
                    return jsonify({"error": "No tienes el rol requerido para acceder a esta ruta."}), 403
                abort(403, description="Acceso denegado: Rol no autorizado.")
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def institution_active_required(f):
    """
    Decorador que bloquea el acceso a una vista si la institución del usuario
    está inactiva (STAT-002). Las cuentas de usuario permanecen activas; solo
    se impide la creación de nuevas solicitudes u otras acciones reservadas a
    planteles activos.

    - Requests JSON/AJAX: devuelve 403 con mensaje JSON.
    - Requests normales: redirige al home del solicitante con un mensaje flash.

    Uso:
        @login_required
        @role_required('applicant')
        @institution_active_required
        def create_request():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return abort(401)

        try:
            from app.models.status_model import Status

            # Solo aplica a usuarios con rol applicant
            is_applicant = any(
                ra.role.name == 'applicant' for ra in getattr(current_user, 'roles_assoc', [])
            ) if getattr(current_user, 'roles_assoc', None) else False

            if not is_applicant:
                return f(*args, **kwargs)

            person = getattr(current_user, 'person', None)
            staff_list = getattr(person, 'institutional_staff', []) if person else []
            if not staff_list:
                # Sin institución afiliada: dejar pasar (otro control gestiona esto)
                return f(*args, **kwargs)

            institution = getattr(staff_list[0], 'institution', None)

            # Cargar la institución si solo tenemos institution_id
            if institution is None and hasattr(staff_list[0], 'institution_id'):
                from app.models.institution_model import Institution
                institution = Institution.query.get(staff_list[0].institution_id)

            if institution is None:
                return f(*args, **kwargs)

            active_status = Status.query.filter_by(status_code='STAT-001').first()
            is_not_active = (active_status and institution.status_id != active_status.id)

            if is_not_active:
                is_ajax = (
                    request.is_json
                    or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                    or (
                        request.accept_mimetypes.accept_json
                        and not request.accept_mimetypes.accept_html
                    )
                )
                if is_ajax:
                    return jsonify({
                        "error": "Tu institución se encuentra inactiva. No es posible realizar esta acción mientras el plantel esté en modo solo lectura."
                    }), 403

                flash(
                    "Tu institución se encuentra inactiva. No es posible realizar esta acción mientras el plantel esté en modo solo lectura.",
                    "warning"
                )
                return redirect(url_for('home_applicant'))

        except Exception as exc:
            # En caso de error inesperado, registrar y dejar pasar (fail-open controlado)
            current_app.logger.error("[institution_active_required] Error verificando estado de institución", exc_info=True)

        return f(*args, **kwargs)
    return decorated_function
