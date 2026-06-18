from functools import wraps
from flask import request, abort, jsonify
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
                # Si la ruta no está registrada como un permiso en BD, denegamos el acceso
                abort(403, description=f"Permiso para la ruta '{endpoint}' no configurado en el sistema.")
                
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
