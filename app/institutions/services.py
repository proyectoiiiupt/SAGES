"""
Servicios del Módulo de Instituciones
Contiene la lógica de negocio para la gestión de instituciones educativas.
"""
from app.models.institution_model import Institution
from app.models.parish_model import Parish
from app.models.municipality_model import Municipality
from app.models.state_model import State
from app.models.educational_level_model import EducationalLevel
from app.models.institution_level_model import InstitutionLevel
from app.models.institution_type_model import InstitutionType
from app.models.institution_scope_model import InstitutionScope
from app.models.institution_dependency_model import InstitutionDependency
from app.models.status_model import Status
from app.models.location_model import Location
from app.models.city_model import City
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.person_model import Person
from app.models.user_model import User
from app.models.position_model import Position
from app.extensions import db
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import re


def get_user_state_info(user):
    """
    Obtiene la información del estado al que pertenece un usuario administrador.
    
    Esta función centraliza la lógica para determinar el estado de un usuario basándose
    en su relación con la empresa a través de la ruta: 
    User -> Person -> CompanyStaff -> Place -> Parish -> Municipality -> State.
    Utiliza state_code en lugar de IDs numéricos para mayor robustez y mantenimiento.
    
    Parámetros:
    - user: objeto User del usuario actual
    
    Retorna:
    - dict con información del estado:
        - state_id: ID del estado
        - state_code: Código del estado
        - state_name: Nombre del estado
    - None si no se puede determinar el estado del usuario
    """
    if not user:
        return None
    
    try:
        from app.models.company_staff_model import CompanyStaff
        from app.models.place_model import Place
        
        user_with_relations = User.query.options(
            joinedload(User.person)
            .joinedload(Person.company_staff)
            .joinedload(CompanyStaff.place)
            .joinedload(Place.parish)
            .joinedload(Parish.municipality)
            .joinedload(Municipality.state)
        ).get(user.id)
        
        if not user_with_relations or not user_with_relations.person:
            return None
        
        person = user_with_relations.person
        if not person.company_staff or len(person.company_staff) == 0:
            return None
        
        company_staff = person.company_staff[0]
        if not company_staff.place:
            return None
        
        place = company_staff.place
        if not place.parish:
            return None
        
        parish = place.parish
        if not parish.municipality:
            return None
        
        municipality = parish.municipality
        if not municipality.state:
            return None
        
        state = municipality.state
        
        return {
            'state_id': state.id,
            'state_code': state.state_code,
            'state_name': state.name
        }
    except Exception as e:
        print(f"Error en get_user_state_info: {e}")
        return None

def get_all_institutions(filters=None, user=None, page=1, per_page=10):
    """
    Obtiene todas las instituciones con sus relaciones cargadas.
    Aplica filtros opcionales y paginación según la lógica exacta de Módulo 18.
    
    Parámetros:
    - filters: dict con filtros (search_name, institution_type, institution_scope, etc.)
    - user: usuario actual para filtrar según rol
    - page: número de página para paginación
    - per_page: cantidad de registros por página
    
    Retorna:
    - dict con instituciones paginadas (con original_index) y metadatos de paginación
    """
    try:
        is_super_admin = False
        if user and user.roles_assoc:
            for role_assoc in user.roles_assoc:
                if role_assoc.role.name == 'super_admin':
                    is_super_admin = True
                    break
        
        user_state_info = None
        if not is_super_admin:
            try:
                user_state_info = get_user_state_info(user)
            except Exception as e:
                print(f"Error obteniendo información del estado: {e}")
                user_state_info = None
        
        query = Institution.query.options(
            joinedload(Institution.institution_type),
            joinedload(Institution.institution_scope),
            joinedload(Institution.institution_dependency),
            joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
            joinedload(Institution.status),
            joinedload(Institution.institution_levels).joinedload(InstitutionLevel.educational_level)
        )

        if user_state_info:
            query = query.join(Parish).join(Municipality).join(State).filter(
                State.state_code == user_state_info['state_code']
            )

        # Base query para calcular índices originales consecutivos
        base_query = Institution.query
        if user_state_info:
            base_query = base_query.join(Parish).join(Municipality).join(State).filter(
                State.state_code == user_state_info['state_code']
            )
        
        all_ids_query = base_query.order_by(Institution.id.asc())
        all_ids = [institution.id for institution in all_ids_query.all()]
        id_to_index = {id: index + 1 for index, id in enumerate(all_ids)}

        query = query.order_by(Institution.id)

        if filters:
            if filters.get('search_name'):
                search_term = filters['search_name']
                try:
                    search_id = int(search_term)
                    query = query.filter(
                        or_(
                            Institution.id == search_id,
                            Institution.institution_name.ilike(f"%{search_term}%")
                        )
                    )
                except ValueError:
                    query = query.filter(Institution.institution_name.ilike(f"%{search_term}%"))
            if filters.get('institution_type'):
                query = query.filter(Institution.institution_type_id == filters['institution_type'])
            if filters.get('institution_scope'):
                query = query.filter(Institution.institution_scope_id == filters['institution_scope'])
            if filters.get('institution_dependency'):
                query = query.filter(Institution.institution_dependency_id == filters['institution_dependency'])
            if filters.get('status'):
                query = query.filter(Institution.status_id == filters['status'])
            if filters.get('state_id'):
                if not user_state_info:
                    query = query.join(Parish).join(Municipality).filter(
                        Municipality.state_id == filters['state_id']
                    )
            if filters.get('parish_id'):
                if user_state_info:
                    parish = db.session.get(Parish, filters['parish_id'])
                    if parish and parish.municipality and parish.municipality.state:
                        if parish.municipality.state.state_code == user_state_info['state_code']:
                            query = query.filter(Institution.parish_id == filters['parish_id'])
                else:
                    query = query.filter(Institution.parish_id == filters['parish_id'])

        total = query.count()
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        institutions_with_index = []
        for institution in pagination.items:
            original_index = id_to_index.get(institution.id, 0)
            institutions_with_index.append({
                'institution': institution,
                'original_index': original_index
            })

        return {
            'institutions': institutions_with_index,
            'total': total,
            'pages': pagination.pages,
            'current_page': pagination.page,
            'per_page': per_page,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'prev_num': pagination.prev_num,
            'next_num': pagination.next_num,
            'total_all': len(all_ids)
        }
    except Exception as e:
        print(f"Error en get_all_institutions: {e}")
        return {
            'institutions': [],
            'total': 0,
            'pages': 0,
            'current_page': 1,
            'per_page': per_page,
            'has_prev': False,
            'has_next': False,
            'prev_num': None,
            'next_num': None,
            'total_all': 0
        }

def get_institution_by_id(institution_id):
    """
    Obtiene una institución específica por su ID con todas sus relaciones cargadas.
    """
    try:
        institution = Institution.query.options(
            joinedload(Institution.institution_type),
            joinedload(Institution.institution_scope),
            joinedload(Institution.institution_dependency),
            joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
            joinedload(Institution.parish).joinedload(Parish.locations).joinedload(Location.city),
            joinedload(Institution.status),
            joinedload(Institution.institution_levels).joinedload(InstitutionLevel.educational_level)
        ).get(institution_id)
        return institution
    except Exception as e:
        print(f"Error en get_institution_by_id: {e}")
        return None

def get_filter_options(user=None):
    """
    Obtiene las opciones disponibles para los filtros del listado de instituciones.
    """
    try:
        institution_types = InstitutionType.query.order_by(InstitutionType.name).all()
        institution_scopes = InstitutionScope.query.order_by(InstitutionScope.name).all()
        institution_dependencies = InstitutionDependency.query.order_by(InstitutionDependency.name).all()
        statuses = Status.query.filter(Status.status_code.in_(['STAT-001', 'STAT-002'])).all()

        is_super_admin = False
        if user and user.roles_assoc:
            for role_assoc in user.roles_assoc:
                if role_assoc.role.name == 'super_admin':
                    is_super_admin = True
                    break
        
        user_state_info = None
        if not is_super_admin:
            try:
                user_state_info = get_user_state_info(user)
            except Exception as e:
                print(f"Error obteniendo información del estado: {e}")
                user_state_info = None

        if user_state_info:
            states = [State.query.filter_by(state_code=user_state_info['state_code']).first()]
            all_parishes = Parish.query.join(Municipality).join(State).filter(
                State.state_code == user_state_info['state_code']
            ).order_by(Parish.name, Parish.id).all()
            
            seen_names = set()
            parishes = []
            for parish in all_parishes:
                if parish.name not in seen_names:
                    seen_names.add(parish.name)
                    parishes.append(parish)
        else:
            states = State.query.order_by(State.name).all()
            all_parishes = Parish.query.order_by(Parish.name, Parish.id).all()
            seen_names = set()
            parishes = []
            for parish in all_parishes:
                if parish.name not in seen_names:
                    seen_names.add(parish.name)
                    parishes.append(parish)

        return {
            'institution_types': institution_types,
            'institution_scopes': institution_scopes,
            'institution_dependencies': institution_dependencies,
            'statuses': statuses,
            'states': states,
            'parishes': parishes
        }
    except Exception as e:
        print(f"Error en get_filter_options: {e}")
        return {
            'institution_types': [],
            'institution_scopes': [],
            'institution_dependencies': [],
            'statuses': [],
            'states': [],
            'parishes': []
        }

def toggle_institution_status(institution_id):
    """
    Alterna el estatus de una institución entre Activo (STAT-001) e Inactivo (STAT-002).
    También actualiza automáticamente el estatus de los usuarios afiliados a la institución.
    """
    try:
        institution = db.session.get(Institution, institution_id)
        if not institution:
            return None, 'Institución no encontrada', 0
        
        active_status = Status.query.filter_by(status_code='STAT-001').first()
        inactive_status = Status.query.filter_by(status_code='STAT-002').first()
        
        if not active_status or not inactive_status:
            return None, 'Estados no configurados correctamente', 0
        
        if institution.status_id == active_status.id:
            institution.status_id = inactive_status.id
            new_institution_status = inactive_status
            new_status = 'Inactivo'
        else:
            institution.status_id = active_status.id
            new_institution_status = active_status
            new_status = 'Activo'
        
        staff_list = InstitutionalStaff.query.options(
            joinedload(InstitutionalStaff.person).joinedload(Person.user).joinedload(User.status)
        ).filter_by(institution_id=institution_id).all()
        
        affected_users_count = 0
        for staff in staff_list:
            if staff.person and staff.person.user:
                user = staff.person.user
                user.status_id = new_institution_status.id
                affected_users_count += 1
        
        db.session.commit()
        db.session.refresh(institution)
        
        return institution, new_status, affected_users_count
    except Exception as e:
        print(f"Error en toggle_institution_status: {e}")
        db.session.rollback()
        return None, f'Error: {str(e)}', 0

def get_institution_users(institution_id, page=1, per_page=10):
    """
    Obtiene los usuarios afiliados a una institución específica con paginación.
    """
    try:
        base_query = InstitutionalStaff.query.filter_by(institution_id=institution_id)
        all_ids_query = base_query.order_by(InstitutionalStaff.id.asc())
        all_ids = [staff.id for staff in all_ids_query.all()]
        id_to_index = {id: index + 1 for index, id in enumerate(all_ids)}
        
        query = InstitutionalStaff.query.options(
            joinedload(InstitutionalStaff.person).joinedload(Person.user),
            joinedload(InstitutionalStaff.position),
            joinedload(InstitutionalStaff.institution)
        ).filter_by(institution_id=institution_id)
        
        total = query.count()
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        users_data = []
        for staff in pagination.items:
            person = staff.person
            user = person.user if person else None
            
            user_status = None
            if user and user.status:
                user_status = {
                    'status_code': user.status.status_code,
                    'status_name': user.status.status_name
                }
            
            original_index = id_to_index.get(staff.id, 0)
            
            user_info = {
                'staff_id': staff.id,
                'person_id': person.id if person else None,
                'person_code': person.person_code if person else 'N/A',
                'full_name': f"{person.first_name} {person.last_name}" if person else 'N/A',
                'identification_type': person.identification_type if person else 'N/A',
                'identification_number': person.identification_number if person else 'N/A',
                'email': person.email if person else 'N/A',
                'mobile': person.mobile if person else 'N/A',
                'position': staff.position.name if staff.position else 'N/A',
                'user_status': user_status,
                'has_user_account': user is not None,
                'original_index': original_index
            }
            users_data.append(user_info)
        
        return {
            'users': users_data,
            'total': total,
            'pages': pagination.pages,
            'current_page': pagination.page,
            'per_page': per_page,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'prev_num': pagination.prev_num,
            'next_num': pagination.next_num,
            'total_all': len(all_ids)
        }
    except Exception as e:
        print(f"Error en get_institution_users: {e}")
        return {
            'users': [],
            'total': 0,
            'pages': 0,
            'current_page': 1,
            'per_page': per_page,
            'has_prev': False,
            'has_next': False,
            'prev_num': None,
            'next_num': None,
            'total_all': 0
        }

def validate_institution_data(institution_data, is_admin=False):
    """
    Valida los datos de una institución antes de actualizar.
    """
    errors = {}
    
    if 'phone' in institution_data:
        phone = institution_data['phone']
        if not phone or phone.strip() == '':
            errors['phone'] = 'El teléfono es obligatorio'
        else:
            clean_phone = phone.replace('(', '').replace(')', '').replace('-', '').strip()
            pattern = r'^\d{11}$'
            if not re.match(pattern, clean_phone):
                errors['phone'] = 'Formato de teléfono inválido. Debe ser (XXXX)-XXXXXXX (ej: (0414)-1234567)'
    
    if 'address' in institution_data:
        address = institution_data['address']
        if not address or address.strip() == '':
            errors['address'] = 'La dirección es obligatoria'
        elif len(address.strip()) < 5:
            errors['address'] = 'La dirección debe tener al menos 5 caracteres'
        elif len(address.strip()) > 200:
            errors['address'] = 'La dirección no puede exceder 200 caracteres'
    
    if is_admin:
        if 'plantel_code' in institution_data:
            plantel_code = institution_data['plantel_code']
            if not plantel_code or plantel_code.strip() == '':
                errors['plantel_code'] = 'El código de plantel es obligatorio'
            else:
                pattern = r'^[A-Z]{3}-[A-Z]{1}[0-9]{4}$'
                if not re.match(pattern, plantel_code.upper()):
                    errors['plantel_code'] = 'Formato de código de plantel inválido. Debe ser XXX-X0000 (ej: DEA-U0001)'
        
        if 'institution_name' in institution_data:
            institution_name = institution_data['institution_name']
            if not institution_name or institution_name.strip() == '':
                errors['institution_name'] = 'El nombre de la institución es obligatorio'
            elif len(institution_name.strip()) < 3:
                errors['institution_name'] = 'El nombre debe tener al menos 3 caracteres'
            elif len(institution_name.strip()) > 100:
                errors['institution_name'] = 'El nombre no puede exceder 100 caracteres'
        
        if 'institution_type_id' in institution_data:
            institution_type_id = institution_data['institution_type_id']
            if not institution_type_id:
                errors['institution_type'] = 'Debe seleccionar un tipo de institución'
            else:
                try:
                    institution_type_id = int(institution_type_id)
                    type_exists = db.session.get(InstitutionType, institution_type_id)
                    if not type_exists:
                        errors['institution_type'] = 'El tipo de institución seleccionado no existe'
                except (ValueError, TypeError):
                    errors['institution_type'] = 'Tipo de institución inválido'
        
        if 'institution_scope_id' in institution_data:
            institution_scope_id = institution_data['institution_scope_id']
            if not institution_scope_id:
                errors['institution_scope'] = 'Debe seleccionar un alcance de institución'
            else:
                try:
                    institution_scope_id = int(institution_scope_id)
                    scope_exists = db.session.get(InstitutionScope, institution_scope_id)
                    if not scope_exists:
                        errors['institution_scope'] = 'El alcance de institución seleccionado no existe'
                except (ValueError, TypeError):
                    errors['institution_scope'] = 'Alcance de institución inválido'
        
        if 'institution_dependency_id' in institution_data:
            institution_dependency_id = institution_data['institution_dependency_id']
            if not institution_dependency_id:
                errors['institution_dependency'] = 'Debe seleccionar una dependencia de institución'
            else:
                try:
                    institution_dependency_id = int(institution_dependency_id)
                    dependency_exists = db.session.get(InstitutionDependency, institution_dependency_id)
                    if not dependency_exists:
                        errors['institution_dependency'] = 'La dependencia de institución seleccionada no existe'
                except (ValueError, TypeError):
                    errors['institution_dependency'] = 'Dependencia de institución inválida'
        
        if 'parish_id' in institution_data:
            parish_id = institution_data['parish_id']
            if not parish_id:
                errors['parish_id'] = 'Debe seleccionar una parroquia'
            else:
                try:
                    parish_id = int(parish_id)
                    parish_exists = db.session.get(Parish, parish_id)
                    if not parish_exists:
                        errors['parish_id'] = 'La parroquia seleccionada no existe'
                except (ValueError, TypeError):
                    errors['parish_id'] = 'Parroquia inválida'
        
        if 'city_id' in institution_data:
            city_id = institution_data['city_id']
            if not city_id:
                errors['city_id'] = 'Debe seleccionar una ciudad'
            else:
                try:
                    city_id = int(city_id)
                    city_exists = db.session.get(City, city_id)
                    if not city_exists:
                        errors['city_id'] = 'La ciudad seleccionada no existe'
                except (ValueError, TypeError):
                    errors['city_id'] = 'Ciudad inválida'
    
    return len(errors) == 0, errors

def update_institution_contact_infrastructure(institution_id, institution_data, is_admin=False):
    """
    Actualiza los datos de contacto e infraestructura de una institución.
    """
    try:
        from app.utils.binnacle_utils import log_action
        from flask_login import current_user
        
        is_valid, validation_errors = validate_institution_data(institution_data, is_admin)
        if not is_valid:
            return None, False, 'Errores de validación: ' + '; '.join(validation_errors.values())
        
        institution = db.session.get(Institution, institution_id)
        if not institution:
            return None, False, 'Institución no encontrada'
        
        old_values = {
            'phone': institution.phone,
            'address': institution.address
        }
        
        if is_admin:
            old_values.update({
                'plantel_code': institution.plantel_code,
                'institution_name': institution.institution_name,
                'institution_type_id': institution.institution_type_id,
                'institution_scope_id': institution.institution_scope_id,
                'institution_dependency_id': institution.institution_dependency_id,
                'parish_id': institution.parish_id,
                'city_id': None
            })
            
            if institution.parish and institution.parish.locations and len(institution.parish.locations) > 0:
                old_values['city_id'] = institution.parish.locations[0].city_id
        
        if 'phone' in institution_data:
            clean_phone = institution_data['phone'].replace('(', '').replace(')', '').replace('-', '').strip()
            institution.phone = clean_phone
        if 'address' in institution_data:
            institution.address = institution_data['address']
        
        if is_admin:
            if 'plantel_code' in institution_data:
                institution.plantel_code = institution_data['plantel_code']
            if 'institution_name' in institution_data:
                institution.institution_name = institution_data['institution_name']
            if 'institution_type_id' in institution_data:
                institution.institution_type_id = institution_data['institution_type_id']
            if 'institution_scope_id' in institution_data:
                institution.institution_scope_id = institution_data['institution_scope_id']
            if 'institution_dependency_id' in institution_data:
                institution.institution_dependency_id = institution_data['institution_dependency_id']
            if 'parish_id' in institution_data:
                institution.parish_id = institution_data['parish_id']
            
            if 'city_id' in institution_data and institution_data['city_id']:
                Location.query.filter_by(parish_id=institution.parish_id).delete()
                city = db.session.get(City, institution_data['city_id'])
                parish = db.session.get(Parish, institution.parish_id)
                if city and parish:
                    new_location = Location(
                        city_id=institution_data['city_id'],
                        parish_id=institution.parish_id,
                        name=f"{city.name} - {parish.name}"
                    )
                    db.session.add(new_location)
        
        db.session.commit()
        db.session.refresh(institution)
        
        try:
            action_description = f'Actualización de datos de institución {institution.institution_code}'
            if is_admin:
                action_description += ' (administrador)'
            else:
                action_description += ' (applicant)'
                
            log_action(
                user_id=current_user.id if current_user.is_authenticated else None,
                module='institutions',
                action_type='UPDATE',
                description=action_description,
                old_values=old_values,
                new_values=institution_data
            )
        except Exception as log_error:
            print(f"Error al registrar en bitácora: {log_error}")
        
        return institution, True, 'Datos actualizados exitosamente'
    except Exception as e:
        print(f"Error en update_institution_contact_infrastructure: {e}")
        db.session.rollback()
        return None, False, f'Error al actualizar: {str(e)}'


def create_institution_invitation(institution_id, invited_by_user, email, identification_number, position_id):
    """Crea una invitación para un colaborador de la institución del solicitante."""
    # Solo un applicant afiliado a la institución puede emitir la invitación.
    from app.models.role_model import Role

    staff_members = invited_by_user.person.institutional_staff if invited_by_user.person else []
    if not any(staff.institution_id == institution_id for staff in staff_members):
        raise PermissionError('No perteneces a esta institución')

    email = email.strip().lower()
    identification_number = identification_number.strip()
    if not email or not identification_number or not position_id:
        raise ValueError('Correo, cédula y cargo son obligatorios')

    # La cédula y el correo no deben pertenecer a un usuario existente.
    existing_person = Person.query.filter(
        or_(
            Person.identification_number == identification_number,
            db.func.lower(Person.email) == email
        )
    ).first()
    if existing_person and existing_person.user:
        raise ValueError('La persona ya tiene un usuario registrado')

    # Validar las referencias antes de generar y enviar el enlace.
    position = db.session.get(Position, position_id)
    institution = db.session.get(Institution, institution_id)
    if not position or not institution:
        raise ValueError('Institución o cargo inválido')

    from app.utils.invitation_utils import create_invitation_token
    from flask import url_for, current_app
    from app.utils.email_utils import send_invitation_email

    token = create_invitation_token(institution_id, position_id, email, identification_number)
    base_url = current_app.config.get('APP_BASE_URL') or os.getenv('APP_BASE_URL', 'http://127.0.0.1:5000')
    ruta_interna = url_for('institutions.delegate_registration', token=token)
    link = f"{base_url.rstrip('/')}{ruta_interna}"
    # Si el correo falla, no se confirma ninguna operación de invitación.
    try:
        send_invitation_email(email, link, institution.institution_name)
    except Exception:
        db.session.rollback()
        raise

    return token


def complete_institution_invitation(payload, data):
    """Crea la persona, usuario, afiliación y rol applicant de una invitación válida."""
    # La cédula y el correo deben coincidir con los datos firmados en el enlace.
    from werkzeug.security import generate_password_hash
    from app.models.role_model import Role
    from app.models.role_user_model import RoleUser

    # Evitar que el enlace se use para registrar otros datos de contacto.
    if data['email'].lower() != payload['email'].lower():
        raise ValueError('El correo no coincide con la invitación')
    if data['identification_number'] != payload['identification_number']:
        raise ValueError('La cédula no coincide con la invitación')
    if Person.query.filter_by(identification_number=data['identification_number']).first():
        raise ValueError('La cédula ya está registrada')
    if Person.query.filter(db.func.lower(Person.email) == data['email'].lower()).first():
        raise ValueError('El correo ya está registrado')

    # El colaborador nace activo y con el rol funcional de solicitante.
    status = Status.query.filter_by(status_code='STAT-001').first()
    role = Role.query.filter_by(name='applicant').first()
    if not status or not role:
        raise ValueError('No están configurados el estado o rol de applicant')

    # Crear la persona y reutilizar sus datos para la cuenta de usuario.
    person = Person(
        person_code=f"PERS-{uuid4().hex[:12].upper()}",
        identification_type=data.get('identification_type', 'V'),
        identification_number=data['identification_number'],
        first_name=data['first_name'],
        second_name=data.get('second_name', ''),
        last_name=data['last_name'],
        middle_name=data.get('middle_name', ''),
        email=data['email'].lower(),
        mobile=data['mobile'],
        phone=data.get('phone') or None
    )
    db.session.add(person)
    db.session.flush()

    user = User(
        user_code=f"USR-{uuid4().hex[:12].upper()}",
        person_id=person.id,
        user_name=person.identification_number,
        password=generate_password_hash(data['password']),
        status_id=status.id
    )
    db.session.add(user)
    db.session.flush()
    # Vincular la cuenta, el rol applicant y el cargo institucional.
    db.session.add(RoleUser(user_id=user.id, role_id=role.id))
    db.session.add(InstitutionalStaff(
        person_id=person.id,
        institution_id=payload['institution_id'],
        position_id=payload['position_id']
    ))
    db.session.commit()
    return user
