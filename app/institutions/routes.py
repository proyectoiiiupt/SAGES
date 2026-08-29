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
    - Restricción a parroquias específicas de Distrito Capital
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
        if current_user.roles_assoc and len(current_user.roles_assoc) > 0 and current_user.roles_assoc[0].role.name == 'state_admin':
            if current_user.person and current_user.person.institutional_staff:
                user_institution = current_user.person.institutional_staff[0].institution
                if user_institution and user_institution.parish and user_institution.parish.municipality:
                    filters['state_id'] = user_institution.parish.municipality.state_id

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
        return render_template('institutions/detail.html', institution=institution, is_applicant=False)
    except Exception as e:
        print(f"Error en view_institution: {e}")
        flash("Error al cargar la institución", 'danger')
        return redirect(url_for('institutions.list_institutions'))

@institutions_bp.route('/<int:institution_id>/users', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
def view_institution_users(institution_id):
    """
    Vista para ver los usuarios afiliados a una institución específica.
    Solo accesible para super_admin y state_admin.
    
    Muestra una tabla con:
    - Información personal (código, nombre, cédula)
    - Contacto (email, móvil)
    - Cargo en la institución
    - Estatus de cuenta de usuario
    """
    try:
        institution = get_institution_by_id(institution_id)
        if not institution:
            abort(404)
        
        # Obtener parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Fijado a 10 filas por página
        
        pagination_data = get_institution_users(institution_id, page=page, per_page=per_page)
        
        return render_template('institutions/affiliates.html',
                             institution=institution,
                             users=pagination_data['users'],
                             pagination=pagination_data)
    except Exception as e:
        print(f"Error en view_institution_users: {e}")
        flash("Error al cargar los usuarios de la institución", 'danger')
        return redirect(url_for('institutions.view_institution', institution_id=institution_id))
