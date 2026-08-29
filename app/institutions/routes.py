"""
Rutas del Módulo de Instituciones
Define los endpoints para la gestión de instituciones educativas.
"""
from flask import render_template, flash, redirect, request, jsonify, abort, url_for
from flask_login import login_required, current_user
from app.institutions import institutions_bp
from app.institutions.services import get_all_institutions, get_institution_by_id, get_filter_options, toggle_institution_status, get_user_state_info
from app.decorators import role_required
from app.models.parish_model import Parish
from app.models.municipality_model import Municipality

@institutions_bp.route('/', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
def list_institutions():
    """
    Vista para listar todas las instituciones con filtros y paginación.
    Solo accesible para super_admin y state_admin.
    
    Funcionalidades:
    - Búsqueda por nombre o ID de institución
    - Filtros por tipo, alcance, dependencia, estatus, estado y parroquia
    - Paginación de 10 registros por página
    - Filtrado automático por estado para administradores estadales
    """
    try:
        # Obtener filtros de la URL
        filters = {
            'search_name': request.args.get('search_name'),
            'institution_type': request.args.get('institution_type'),
            'institution_scope': request.args.get('institution_scope'),
            'institution_dependency': request.args.get('institution_dependency'),
            'status': request.args.get('status'),
            'state_id': request.args.get('state_id'),
            'parish_id': request.args.get('parish_id')
        }

        # Convertir a enteros los filtros que no estén vacíos (excepto search_name)
        filters = {k: int(v) if v and k != 'search_name' else v for k, v in filters.items()}

        # Para administrador estadal, filtrar automáticamente por su estado
        # Verificar si el usuario es super admin
        is_super_admin = False
        if current_user and current_user.roles_assoc:
            for role_assoc in current_user.roles_assoc:
                if role_assoc.role.name == 'super_admin':
                    is_super_admin = True
                    break
        
        # Solo aplicar filtro automático para admin estatal
        if not is_super_admin:
            user_state_info = get_user_state_info(current_user)
            if user_state_info:
                filters['state_id'] = user_state_info['state_id']

        # Obtener parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Fijado a 10 filas por página

        # Obtener datos paginados y opciones de filtros
        pagination_data = get_all_institutions(filters, current_user, page=page, per_page=per_page)
        filter_options = get_filter_options(current_user)

        return render_template('institutions/list.html',
                             institutions=pagination_data['institutions'],
                             pagination=pagination_data,
                             filter_options=filter_options,
                             current_filters=filters)
    except Exception as e:
        print(f"Error en list_institutions: {e}")
        flash("Error al cargar las instituciones", 'danger')
        return render_template('institutions/list.html',
                             institutions=[],
                             pagination={'total': 0, 'pages': 0, 'current_page': 1, 'has_prev': False, 'has_next': False},
                             filter_options={'institution_types': [], 'institution_scopes': [], 'institution_dependencies': [], 'statuses': [], 'states': [], 'parishes': []},
                             current_filters={})

@institutions_bp.route('/<int:institution_id>', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
def view_institution(institution_id):
    """
    Vista para ver detalles de una institución específica.
    Solo accesible para super_admin y state_admin.
    
    Muestra información completa:
    - Datos generales (código, nombre, dirección, teléfono)
    - Clasificación (tipo, alcance, dependencia)
    - Niveles educativos
    - Ubicación (parroquia, municipio, estado)
    - Información del sistema (fechas de creación/actualización)
    - Control de estatus (Activo/Inactivo)
    """
    try:
        institution = get_institution_by_id(institution_id)
        if not institution:
            abort(404)
        return render_template('institutions/detail.html', institution=institution)
    except Exception as e:
        print(f"Error en view_institution: {e}")
        flash("Error al cargar la institución", 'danger')
        return redirect(url_for('institutions.list_institutions'))

@institutions_bp.route('/<int:institution_id>/toggle-status', methods=['POST'])
@login_required
@role_required('super_admin', 'state_admin')
def toggle_institution_status_route(institution_id):
    """
    Ruta AJAX para alternar el estatus de una institución entre Activo e Inactivo.
    Solo accesible para super_admin y state_admin.
    
    Retorna JSON con:
    - success: booleano indicando éxito/error
    - message: mensaje descriptivo
    - new_status: nuevo estatus ('Activo' o 'Inactivo')
    - status_code: código del estatus en base de datos
    """
    try:
        institution, new_status = toggle_institution_status(institution_id)
        
        if institution is None:
            return jsonify({'success': False, 'message': new_status}), 404
        
        return jsonify({
            'success': True,
            'message': f'Institución cambiada a {new_status}',
            'new_status': new_status,
            'status_code': institution.status.status_code
        })
    except Exception as e:
        print(f"Error en toggle_institution_status_route: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@institutions_bp.route('/api/parishes-by-state/<int:state_id>', methods=['GET'])
@login_required
def get_parishes_by_state(state_id):
    """
    API endpoint para obtener parroquias filtradas por estado.
    Utilizado para actualizar dinámicamente el filtro de parroquias cuando se selecciona un estado.
    """
    try:
        parishes = Parish.query.join(Municipality).filter(
            Municipality.state_id == state_id
        ).order_by(Parish.name, Parish.id).all()
        
        parishes_data = [{'id': parish.id, 'name': parish.name} for parish in parishes]
        
        return jsonify({'parishes': parishes_data})
    except Exception as e:
        print(f"Error en get_parishes_by_state: {e}")
        return jsonify({'parishes': []}), 500