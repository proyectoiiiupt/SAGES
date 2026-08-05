"""
Rutas del Módulo de Instituciones
Define los endpoints para la gestión de instituciones educativas.
"""
from flask import render_template, flash, redirect, request, jsonify, abort, url_for
from flask_login import login_required, current_user
from app.institutions import institutions_bp
from app.institutions.services import get_all_institutions, get_institution_by_id, get_filter_options, toggle_institution_status, get_institution_users, update_institution_contact_infrastructure
from app.decorators import role_required

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

@institutions_bp.route('/<int:institution_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('applicant')
def edit_institution(institution_id):
    """
    Vista para editar los datos de contacto de una institución.
    Exclusivamente accesible para applicants (solo su institución afiliada).
    
    Funcionalidades:
    - Actualizar datos de contacto (teléfono)
    - Campos bloqueados: plantel_code y ubicación (parroquia, municipio, estado)
    """
    try:
        # Verificar que el usuario tenga persona y personal institucional
        if not current_user.person or not current_user.person.institutional_staff:
            flash("No tienes una institución afiliada.", 'warning')
            return redirect(url_for('home_applicant'))
        
        # Verificar que la institución sea la suya
        user_staff = current_user.person.institutional_staff[0]
        if user_staff.institution_id != institution_id:
            flash("No tienes permiso para editar esta institución.", 'danger')
            return redirect(url_for('institutions.my_institution'))
        
        institution = get_institution_by_id(institution_id)
        if not institution:
            abort(404)
        
        # Obtener opciones para los select
        from app.models.institution_type_model import InstitutionType
        from app.models.institution_scope_model import InstitutionScope
        from app.models.institution_dependency_model import InstitutionDependency
        
        institution_types = InstitutionType.query.order_by(InstitutionType.name).all()
        institution_scopes = InstitutionScope.query.order_by(InstitutionScope.name).all()
        institution_dependencies = InstitutionDependency.query.order_by(InstitutionDependency.name).all()
        
        # Crear lista de dependencias para el frontend
        dependencies_list = [{'id': dep.id, 'name': dep.name} for dep in institution_dependencies]
        
        # Depuración: verificar qué datos tenemos
        print(f"Dependencias encontradas: {dependencies_list}")
        
        if request.method == 'POST':
            # Recopilar datos de la institución
            institution_data = {
                'phone': request.form.get('phone'),
                'institution_name': request.form.get('institution_name'),
                'institution_type_id': request.form.get('institution_type'),
                'institution_scope_id': request.form.get('institution_scope'),
                'institution_dependency_id': request.form.get('institution_dependency'),
                'address': request.form.get('address')
            }
            
            # Convertir campos numéricos
            if institution_data['institution_type_id']:
                institution_data['institution_type_id'] = int(institution_data['institution_type_id'])
            if institution_data['institution_scope_id']:
                institution_data['institution_scope_id'] = int(institution_data['institution_scope_id'])
            if institution_data['institution_dependency_id']:
                institution_data['institution_dependency_id'] = int(institution_data['institution_dependency_id'])
            
            # Actualizar institución
            institution, success, message = update_institution_contact_infrastructure(
                institution_id, institution_data
            )
            
            print(f"Resultado de actualización: success={success}, message={message}")
            if success:
                print(f"Teléfono después de actualizar: {institution.phone}")
            
            if success:
                flash(message, 'success')
                return redirect(url_for('institutions.my_institution'))
            else:
                # Verificar si es un error de validación
                if 'Errores de validación:' in message:
                    # Extraer errores específicos para mostrar en el formulario
                    validation_errors = {}
                    error_parts = message.replace('Errores de validación: ', '').split('; ')
                    for error in error_parts:
                        if ':' in error:
                            field, error_msg = error.split(':', 1)
                            validation_errors[field.strip()] = error_msg.strip()
                    
                    flash('Por favor, corrija los errores en el formulario.', 'danger')
                    return render_template('institutions/edit.html', institution=institution, is_applicant=True, 
                                         institution_types=institution_types, institution_scopes=institution_scopes, 
                                         institution_dependencies=institution_dependencies, dependencies_list=dependencies_list,
                                         validation_errors=validation_errors, form_data=institution_data)
                else:
                    flash(message, 'danger')
                    return render_template('institutions/edit.html', institution=institution, is_applicant=True, 
                                         institution_types=institution_types, institution_scopes=institution_scopes, 
                                         institution_dependencies=institution_dependencies, dependencies_list=dependencies_list)
        
        return render_template('institutions/edit.html', institution=institution, is_applicant=True,
                             institution_types=institution_types, institution_scopes=institution_scopes,
                             institution_dependencies=institution_dependencies, dependencies_list=dependencies_list)
    except Exception as e:
        print(f"Error en edit_institution: {e}")
        flash("Error al procesar la solicitud", 'danger')
        return redirect(url_for('institutions.my_institution'))

@institutions_bp.route('/my-institution', methods=['GET'])
@login_required
@role_required('applicant')
def my_institution():
    """
    Vista para que el usuario (applicant) vea directamente su institución afiliada.
    Solo accesible para usuarios con rol applicant.
    
    Muestra el detalle de la institución a la que está afiliado el usuario actual.
    """
    try:
        # Verificar que el usuario tiene persona y personal institucional
        if not current_user.person or not current_user.person.institutional_staff:
            flash("No tienes una institución afiliada.", 'warning')
            return redirect(url_for('home_applicant'))
        
        # Obtener la institución del usuario
        user_staff = current_user.person.institutional_staff[0]
        institution = get_institution_by_id(user_staff.institution_id)
        
        if not institution:
            flash("Institución no encontrada.", 'danger')
            return redirect(url_for('home_applicant'))
        
        return render_template('institutions/detail.html', institution=institution, is_applicant=True)
    except Exception as e:
        print(f"Error en my_institution: {e}")
        flash("Error al cargar tu institución.", 'danger')
        return redirect(url_for('home_applicant'))