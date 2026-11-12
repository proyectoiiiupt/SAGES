from functools import wraps
from flask import request, abort, jsonify, flash, redirect, url_for
from flask_login import current_user
from app.models.permission_model import Permission

def check_permissions(view_name=None):
    """
    Decorador para validar si el rol del usuario en sesión tiene
    permisos sobre la vista solicitada.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return abort(401)
                
            # Usar view_name si se proporciona, sino usar el endpoint actual (ej: 'auth.login')
            endpoint = view_name or request.endpoint
            
            permission = Permission.query.filter_by(view=endpoint).first()
            
            if not permission:
                import logging
                logging.warning(f"Permiso no configurado para endpoint '{endpoint}', user_id={current_user.id}")
                # Si la ruta no está registrada como un permiso en BD, denegamos el acceso
                abort(403, description="No tienes permisos para acceder a esta ruta.")
                
            has_permission = False
            # Buscar si alguno de los roles del usuario tiene el permiso
            for role_assoc in current_user.roles_assoc:
                for perm_assoc in role_assoc.role.permissions_assoc:
                    if perm_assoc.permission_id == permission.id:
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

            inactive_status = Status.query.filter_by(status_code='STAT-002').first()
            if inactive_status and institution.status_id == inactive_status.id:
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
                    "Tu institución se encuentra inactiva. No puedes crear nuevas solicitudes mientras el plantel esté en modo solo lectura.",
                    "warning"
                )
                return redirect(url_for('home_applicant'))

        except Exception as exc:
            # En caso de error inesperado, registrar y dejar pasar (fail-open controlado)
            print(f"[institution_active_required] Error verificando estado de institución: {exc}")

        return f(*args, **kwargs)
    return decorated_function
