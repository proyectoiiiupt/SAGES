"""
Rutas del Módulo de Instituciones
Define los endpoints para la gestión de instituciones educativas.
"""
import re

from flask import render_template, flash, redirect, request, jsonify, abort, url_for
from flask_login import login_required, current_user
from app.institutions import institutions_bp
from app.institutions.services import (
    get_all_institutions, get_institution_by_id, get_filter_options,
    toggle_institution_status, get_institution_users, update_institution_contact_infrastructure,
    get_user_state_info, create_institution_invitation, complete_institution_invitation
)
from app.decorators import role_required
from app.models.municipality_model import Municipality
from app.models.parish_model import Parish
from app.models.city_model import City
from app.models.state_model import State
from app.models.position_model import Position
from app.institutions.forms import InstitutionEditForm, InstitutionEditApplicantForm
from app.extensions import db
from app.utils.invitation_utils import read_invitation_token

EMAIL_REGEX = re.compile(r'^[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$')


def _has_valid_email_domain(email):
    """Comprueba si el dominio del correo tiene registros MX.
    Esto valida que el dominio existe, no que la casilla exacta exista.
    """
    domain = email.rsplit('@', 1)[1].lower()
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX')
        return bool(answers)
    except Exception:
        return None


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

        # Convertir a enteros los filtros numéricos
        filters = {k: int(v) if v and k != 'search_name' else v for k, v in filters.items()}

        # Para administrador estadal, filtrar automáticamente por su estado
        is_super_admin = False
        if current_user and current_user.roles_assoc:
            for role_assoc in current_user.roles_assoc:
                if role_assoc.role.name == 'super_admin':
                    is_super_admin = True
                    break
        
        if not is_super_admin:
            user_state_info = get_user_state_info(current_user)
            if user_state_info:
                filters['state_id'] = user_state_info['state_id']

        page = request.args.get('page', 1, type=int)
        per_page = 10

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
    """
    try:
        institution = get_institution_by_id(institution_id)
        if not institution:
            abort(404)
        
        show_success = request.args.get('success', 'false') == 'true'
        
        return render_template('institutions/detail.html', institution=institution, is_applicant=False, show_success=show_success)
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
    """
    try:
        institution, new_status, affected_users = toggle_institution_status(institution_id)
        
        if institution is None:
            return jsonify({'success': False, 'message': new_status, 'affected_users': 0}), 404
        
        return jsonify({
            'success': True,
            'message': f'Institución cambiada a {new_status} exitosamente',
            'new_status': new_status,
            'status_code': institution.status.status_code,
            'affected_users': affected_users
        })
    except Exception as e:
        print(f"Error en toggle_institution_status_route: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}', 'affected_users': 0}), 500

@institutions_bp.route('/<int:institution_id>/users', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin', 'applicant')
def view_institution_users(institution_id):
    """
    Vista para ver los usuarios afiliados a una institución específica.
    """
    try:
        is_applicant = any(
            role_assoc.role.name == 'applicant'
            for role_assoc in current_user.roles_assoc
        )
        if is_applicant:
            staff_members = current_user.person.institutional_staff if current_user.person else []
            if not staff_members or staff_members[0].institution_id != institution_id:
                abort(403)

        institution = get_institution_by_id(institution_id)
        if not institution:
            abort(404)
        
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        pagination_data = get_institution_users(institution_id, page=page, per_page=per_page)
        
        return render_template('institutions/affiliates.html',
                             institution=institution,
                             users=pagination_data['users'],
                             pagination=pagination_data)
    except Exception as e:
        print(f"Error en view_institution_users: {e}")
        flash("Error al cargar los usuarios de la institución", 'danger')
        user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else None
        if user_role == 'applicant':
            return redirect(url_for('institutions.my_institution'))
        return redirect(url_for('institutions.view_institution', institution_id=institution_id))

@institutions_bp.route('/<int:institution_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('applicant', 'state_admin', 'super_admin')
def edit_institution(institution_id):
    """
    Vista para editar los datos de una institución.
    """
    try:
        user_role = None
        if current_user.roles_assoc and len(current_user.roles_assoc) > 0:
            user_role = current_user.roles_assoc[0].role.name
        
        if user_role == 'applicant':
            if not current_user.person or not current_user.person.institutional_staff or len(current_user.person.institutional_staff) == 0:
                flash("No tienes una institución afiliada.", 'warning')
                return redirect(url_for('home_applicant'))
            
            user_staff = current_user.person.institutional_staff[0]
            if user_staff.institution_id != institution_id:
                flash("No tienes permiso para editar esta institución.", 'danger')
                return redirect(url_for('institutions.my_institution'))
        
        institution = get_institution_by_id(institution_id)
        if not institution:
            abort(404)
        
        from app.models.institution_type_model import InstitutionType
        from app.models.institution_scope_model import InstitutionScope
        from app.models.institution_dependency_model import InstitutionDependency
        
        institution_types = InstitutionType.query.order_by(InstitutionType.name).all()
        institution_scopes = InstitutionScope.query.order_by(InstitutionScope.name).all()
        institution_dependencies = InstitutionDependency.query.order_by(InstitutionDependency.name).all()
        
        dependencies_list = [{'id': dep.id, 'name': dep.name} for dep in institution_dependencies]
        
        current_city_id = None
        try:
            if institution.parish and institution.parish.locations and len(institution.parish.locations) > 0:
                location = institution.parish.locations[0]
                if location and hasattr(location, 'city_id'):
                    current_city_id = location.city_id
        except Exception:
            current_city_id = None
        
        if user_role == 'applicant':
            form = InstitutionEditApplicantForm()
        else:
            form = InstitutionEditForm()
        
        if request.method == 'GET':
            phone_value = institution.phone
            if phone_value and len(phone_value) == 11 and not phone_value.startswith('('):
                phone_value = '(' + phone_value[:4] + ')-' + phone_value[4:]
            
            form.phone.data = phone_value
            form.address.data = institution.address
            
            if user_role != 'applicant':
                form.plantel_code.data = institution.plantel_code
                form.institution_name.data = institution.institution_name
                form.institution_type.data = str(institution.institution_type_id) if institution.institution_type_id else ''
                form.institution_scope.data = str(institution.institution_scope_id) if institution.institution_scope_id else ''
                form.institution_dependency.data = str(institution.institution_dependency_id) if institution.institution_dependency_id else ''
                
                try:
                    if institution.parish and institution.parish.municipality and institution.parish.municipality.state:
                        form.state_id.data = str(institution.parish.municipality.state_id)
                    else:
                        form.state_id.data = ''
                except Exception:
                    form.state_id.data = ''
                
                try:
                    if institution.parish and institution.parish.municipality:
                        form.municipality_id.data = str(institution.parish.municipality_id)
                    else:
                        form.municipality_id.data = ''
                except Exception:
                    form.municipality_id.data = ''
                
                try:
                    if institution.parish:
                        form.parish_id.data = str(institution.parish_id)
                    else:
                        form.parish_id.data = ''
                except Exception:
                    form.parish_id.data = ''
                
                form.city_id.data = str(current_city_id) if current_city_id else ''
            
            return render_template('institutions/edit.html', institution=institution, is_applicant=(user_role == 'applicant'),
                                 institution_types=institution_types, institution_scopes=institution_scopes,
                                 institution_dependencies=institution_dependencies, dependencies_list=dependencies_list,
                                 current_city_id=current_city_id, form=form)
        
        elif request.method == 'POST':
            if not form.validate():
                flash('Por favor, corrija los errores en el formulario.', 'danger')
                return render_template('institutions/edit.html', institution=institution, is_applicant=(user_role == 'applicant'),
                                     institution_types=institution_types, institution_scopes=institution_scopes,
                                     institution_dependencies=institution_dependencies, dependencies_list=dependencies_list,
                                     current_city_id=current_city_id, form=form)
            
            institution_data = {
                'phone': form.phone.data,
                'address': form.address.data
            }
            
            if user_role != 'applicant':
                institution_data.update({
                    'plantel_code': form.plantel_code.data,
                    'institution_name': form.institution_name.data,
                    'institution_type_id': int(form.institution_type.data) if form.institution_type.data else None,
                    'institution_scope_id': int(form.institution_scope.data) if form.institution_scope.data else None,
                    'institution_dependency_id': int(form.institution_dependency.data) if form.institution_dependency.data else None,
                    'parish_id': int(form.parish_id.data) if form.parish_id.data else None,
                    'city_id': int(form.city_id.data) if form.city_id.data else None
                })
            
            institution, success, message = update_institution_contact_infrastructure(
                institution_id, institution_data, is_admin=(user_role != 'applicant')
            )
            
            if success:
                if user_role == 'applicant':
                    return redirect(url_for('institutions.my_institution', success='true'))
                else:
                    return redirect(url_for('institutions.view_institution', institution_id=institution_id, success='true'))
            else:
                flash(message, 'danger')
                return render_template('institutions/edit.html', institution=institution, is_applicant=(user_role == 'applicant'),
                                     institution_types=institution_types, institution_scopes=institution_scopes,
                                     institution_dependencies=institution_dependencies, dependencies_list=dependencies_list,
                                     current_city_id=current_city_id, form=form)
    except Exception as e:
        print(f"Error en edit_institution: {e}")
        flash("Error al procesar la solicitud", 'danger')
        user_role = None
        if current_user.roles_assoc and len(current_user.roles_assoc) > 0:
            user_role = current_user.roles_assoc[0].role.name
        
        if user_role == 'applicant':
            return redirect(url_for('institutions.my_institution'))
        else:
            return redirect(url_for('institutions.view_institution', institution_id=institution_id))

@institutions_bp.route('/my-institution', methods=['GET'])
@login_required
@role_required('applicant')
def my_institution():
    """
    Vista para que el usuario (applicant) vea directamente su institución afiliada.
    """
    try:
        if not current_user.person or not current_user.person.institutional_staff or len(current_user.person.institutional_staff) == 0:
            flash("No tienes una institución afiliada. Contacta al administrador.", 'warning')
            return redirect(url_for('home_applicant'))
        
        user_staff = current_user.person.institutional_staff[0]
        institution = get_institution_by_id(user_staff.institution_id)
        
        if not institution:
            flash("Institución no encontrada. Contacta al administrador.", 'danger')
            return redirect(url_for('home_applicant'))
        
        show_success = request.args.get('success', 'false') == 'true'
        
        return render_template('institutions/detail.html', institution=institution, is_applicant=True, show_success=show_success)
    except Exception as e:
        print(f"Error en my_institution: {e}")
        flash("Error al cargar tu institución. Contacta al administrador.", 'danger')
        return redirect(url_for('home_applicant'))

@institutions_bp.route('/api/parishes-by-state/<int:state_id>', methods=['GET'])
@login_required
def get_parishes_by_state(state_id):
    """
    API endpoint para obtener parroquias filtradas por estado.
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

@institutions_bp.route('/api/states', methods=['GET'])
@login_required
def get_states_api():
    try:
        states = State.query.order_by(State.name).all()
        return jsonify([{'id': s.id, 'name': s.name} for s in states])
    except Exception as e:
        print(f"Error en get_states_api: {e}")
        return jsonify({'error': str(e)}), 500

@institutions_bp.route('/api/cities', methods=['GET'])
@login_required
def get_cities_api():
    try:
        parish_id = request.args.get('parish_id', type=int)
        if parish_id:
            from app.models.location_model import Location
            locations = Location.query.filter_by(parish_id=parish_id).all()
            city_ids = [loc.city_id for loc in locations]
            cities = City.query.filter(City.id.in_(city_ids)).order_by(City.name).all()
            return jsonify([{'id': c.id, 'name': c.name} for c in cities])
        else:
            return jsonify([])
    except Exception as e:
        print(f"Error en get_cities_api: {e}")
        return jsonify({'error': str(e)}), 500

@institutions_bp.route('/api/municipalities/<int:state_id>', methods=['GET'])
@login_required
def get_municipalities_api(state_id):
    try:
        municipalities = Municipality.query.filter_by(state_id=state_id).order_by(Municipality.name).all()
        return jsonify([{'id': m.id, 'name': m.name} for m in municipalities])
    except Exception as e:
        print(f"Error en get_municipalities_api: {e}")
        return jsonify({'error': str(e)}), 500

@institutions_bp.route('/api/parishes/<int:municipality_id>', methods=['GET'])
@login_required
def get_parishes_api(municipality_id):
    try:
        parishes = Parish.query.filter_by(municipality_id=municipality_id).order_by(Parish.name).all()
        return jsonify([{'id': p.id, 'name': p.name} for p in parishes])
    except Exception as e:
        print(f"Error en get_parishes_api: {e}")
        return jsonify({'error': str(e)}), 500


@institutions_bp.route('/<int:institution_id>/users/invite', methods=['GET', 'POST'])
@login_required
@role_required('applicant')
def invite_institution_collaborator(institution_id):
    # La invitación solo está disponible para applicants afiliados a la institución.
    institution = get_institution_by_id(institution_id)
    if not institution:
        abort(404)

    staff_members = current_user.person.institutional_staff if current_user.person else []
    if not any(staff.institution_id == institution_id for staff in staff_members):
        abort(403)

    # Los cargos se muestran desde la tabla positions para conservar sus referencias.
    positions = Position.query.order_by(Position.name).all()
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
        try:
            create_institution_invitation(
                institution_id=institution_id,
                invited_by_user=current_user,
                email=request.form.get('email', ''),
                identification_number=request.form.get('identification_number', ''),
                position_id=request.form.get('position_id', type=int)
            )
            msg = 'La invitación fue enviada correctamente.'
            if is_ajax:
                return jsonify({'success': True, 'message': msg}), 200
            flash(msg, 'success')
            return redirect(url_for('institutions.view_institution_users', institution_id=institution_id))
        except (PermissionError, ValueError, RuntimeError) as error:
            from app.extensions import db
            db.session.rollback()
            msg = str(error)
            if is_ajax:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'danger')
        except Exception as error:
            from app.extensions import db
            db.session.rollback()
            msg = f'Error al enviar la invitación: {str(error)}'
            if is_ajax:
                return jsonify({'success': False, 'message': msg}), 500
            flash(msg, 'danger')

    return render_template('institutions/invite.html', institution=institution, positions=positions)


@institutions_bp.route('/api/validate-identification', methods=['GET'])
@login_required
def validate_identification():
    """
    API endpoint para validar si una cédula ya está registrada en el sistema.
    Retorna JSON indicando si la cédula existe.
    """
    try:
        identification_number = request.args.get('identification_number', '').strip()

        if not identification_number:
            return jsonify({'exists': False, 'message': 'Cédula no proporcionada'}), 400

        from app.models.person_model import Person
        existing_person = Person.query.filter_by(identification_number=identification_number).first()

        if existing_person:
            return jsonify({
                'exists': True,
                'message': f'La cédula "{identification_number}" ya está registrada en el sistema'
            })
        else:
            return jsonify({'exists': False, 'message': 'Cédula disponible'})

    except Exception as e:
        print(f"Error en validate_identification: {e}")
        return jsonify({'exists': False, 'message': 'Error al validar cédula'}), 500


@institutions_bp.route('/api/validate-email', methods=['GET'])
@login_required
def validate_email():
    """
    API endpoint para validar si un correo electrónico es válido y si el dominio existe.
    Verifica también si ya está registrado en la base de datos.
    """
    try:
        email = request.args.get('email', '').strip().lower()

        if not email:
            return jsonify({'exists': False, 'valid': False, 'message': 'Correo no proporcionado'}), 400

        if not EMAIL_REGEX.match(email):
            return jsonify({
                'exists': False,
                'valid': False,
                'message': 'El formato del correo electrónico no es válido'
            })

        from sqlalchemy import func
        from app.models.person_model import Person

        # Búsqueda insensible a mayúsculas/minúsculas para evitar fallos por diferencias de casing
        existing_person = Person.query.filter(func.lower(Person.email) == email).first()
        if existing_person:
            return jsonify({
                'exists': True,
                'valid': True,
                'message': f'El correo "{email}" ya está registrado en el sistema'
            })

        domain_exists = _has_valid_email_domain(email)
        if domain_exists is False:
            return jsonify({
                'exists': False,
                'valid': False,
                'message': 'El dominio del correo no existe o no tiene un registro MX válido'
            })

        return jsonify({
            'exists': False,
            'valid': True,
            'message': 'Correo disponible y con dominio válido'
        })

    except Exception as e:
        print(f"Error en validate_email: {e}")
        return jsonify({'exists': False, 'valid': False, 'message': 'Error al validar correo'}), 500


@institutions_bp.route('/pre-registration/', methods=['GET', 'POST'])
@institutions_bp.route('/pre-registration/delegado', methods=['GET', 'POST'])
def delegate_registration():
    token = request.args.get('token') or request.form.get('token')
    payload = read_invitation_token(token) if token else None
    if not payload:
        return jsonify({'error': 'Token de invitación inválido o expirado.'}), 400
    return jsonify({
        'message': 'Invitación válida. El registro del colaborador pertenece a otra rama.',
        'institution_id': payload.get('institution_id'),
        'position_id': payload.get('position_id'),
        'email': payload.get('email')
    }), 200

