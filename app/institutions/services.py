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
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
import re

# Código del estado en la tabla State al que se restringe el sistema.
# Usar código en lugar de nombre para mayor precisión
DC_STATE_CODE = "ST-024"  # Distrito Capital
DC_STATE_NAME = "Distrito Capital"  # Backup por si se necesita

# Lista oficial de las 22 parroquias de Distrito Capital (Caracas)
DC_PARISHES = [
    "23 de enero", "Altagracia", "Antímano", "Caricuao", "Catedral", 
    "Coche", "El Junquito", "El Paraíso", "El Recreo", "El Valle", 
    "La Candelaria", "La Pastora", "La Vega", "Macarao", "San Agustín", 
    "San Bernardino", "San José", "San Juan", "San Pedro", "Santa Rosalía", 
    "Santa Teresa", "Sucre (Catia)"
]

def get_all_institutions(filters=None, user=None, page=1, per_page=10):
    """
    Obtiene todas las instituciones con sus relaciones cargadas.
    Aplica filtros opcionales y paginación.
    
    Parámetros:
    - filters: dict con filtros (search_name, institution_type, institution_scope, etc.)
    - user: usuario actual para filtrar según rol
    - page: número de página para paginación
    - per_page: cantidad de registros por página
    
    Retorna:
    - dict con instituciones paginadas y metadatos de paginación
    
    Restricciones:
    - Solo muestra instituciones de parroquias específicas de Distrito Capital
    - Administradores estadales solo ven instituciones de su estado
    - Super admin ve todas las instituciones permitidas
    """
    try:
        # Cargar relaciones optimizadamente para evitar N+1 queries
        query = Institution.query.options(
            joinedload(Institution.institution_type),
            joinedload(Institution.institution_scope),
            joinedload(Institution.institution_dependency),
            joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
            joinedload(Institution.status),
            joinedload(Institution.institution_levels).joinedload(InstitutionLevel.educational_level)
        )

        # Para administrador estadal, filtrar por las parroquias reales de su estado
        if user and user.person and user.person.institutional_staff:
            user_institution = user.person.institutional_staff[0].institution
            if user_institution and user_institution.parish and user_institution.parish.municipality:
                user_state_id = user_institution.parish.municipality.state_id
                # Si es Distrito Capital, filtrar por lista oficial de parroquias Y estado
                if user_state_id == 24:  # ID de Distrito Capital
                    # Agregar joins necesarios para evitar duplicados
                    query = query.join(Parish).join(Municipality).join(State).filter(
                        Parish.name.in_(DC_PARISHES),
                        State.state_code == DC_STATE_CODE
                    )
                else:
                    # Para otros estados, filtrar por estado (se podría agregar listas similares)
                    query = query.join(Parish).join(Municipality).filter(
                        Municipality.state_id == user_state_id
                    )
            else:
                query = query.join(Parish)
        else:
            # Para super admin: restringir a las parroquias reales de Distrito Capital
            # Filtrar por lista oficial de parroquias de Caracas Y estado para evitar duplicados
            # También incluir joins necesarios para filtros posteriores
            query = (
                query.join(Parish)
                .join(Municipality)
                .join(State)
                .filter(
                    Parish.name.in_(DC_PARISHES),
                    State.state_code == DC_STATE_CODE
                )
            )

        # Ordenar por ID de institución
        query = query.order_by(Institution.id)

        # Aplicar filtros si se proporcionan
        if filters:
            if filters.get('search_name'):
                # Buscar por nombre o ID
                search_term = filters['search_name']
                # Intentar convertir a entero para búsqueda por ID
                try:
                    search_id = int(search_term)
                    # Si es un número válido, buscar por ID o nombre
                    query = query.filter(
                        or_(
                            Institution.id == search_id,
                            Institution.institution_name.ilike(f"%{search_term}%")
                        )
                    )
                except ValueError:
                    # Si no es un número, buscar solo por nombre
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
                # Asegurar que los joins necesarios estén presentes
                # Si el filtro ya fue aplicado por super admin con restricción DC, 
                # sobrescribirlo cuando el usuario selecciona explícitamente otro estado
                state_id = filters['state_id']
                
                # Para super admin, si selecciona un estado diferente a DC, remover restricción de parroquias
                if not user or not (user.person and user.person.institutional_staff):
                    if state_id != 24:  # Si no es Distrito Capital
                        # Reconstruir query sin restricción de parroquias DC
                        query = Institution.query.options(
                            joinedload(Institution.institution_type),
                            joinedload(Institution.institution_scope),
                            joinedload(Institution.institution_dependency),
                            joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
                            joinedload(Institution.status),
                            joinedload(Institution.institution_levels).joinedload(InstitutionLevel.educational_level)
                        ).join(Parish).join(Municipality).join(State)
                
                query = query.filter(Municipality.state_id == state_id)
            if filters.get('parish_id'):
                query = query.filter(Institution.parish_id == filters['parish_id'])

        # Obtener total de registros para paginación
        total = query.count()

        # Aplicar paginación
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            'institutions': pagination.items,
            'total': total,
            'pages': pagination.pages,
            'current_page': pagination.page,
            'per_page': per_page,
            'has_prev': pagination.has_prev,
            'has_next': pagination.has_next,
            'prev_num': pagination.prev_num,
            'next_num': pagination.next_num
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
            'next_num': None
        }

def get_institution_by_id(institution_id):
    """
    Obtiene una institución específica por su ID con todas sus relaciones cargadas.
    
    Parámetros:
    - institution_id: ID de la institución a buscar
    
    Retorna:
    - objeto Institution si existe, None si no se encuentra
    """
    try:
        institution = Institution.query.options(
            joinedload(Institution.institution_type),
            joinedload(Institution.institution_scope),
            joinedload(Institution.institution_dependency),
            joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
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
    Si se proporciona un usuario, filtra las parroquias según su estado.
    
    Parámetros:
    - user: usuario actual para filtrar parroquias según su estado
    
    Retorna:
    - dict con listas de opciones para cada filtro
    """
    try:
        # Obtener opciones de clasificación
        institution_types = InstitutionType.query.order_by(InstitutionType.name).all()
        institution_scopes = InstitutionScope.query.order_by(InstitutionScope.name).all()
        institution_dependencies = InstitutionDependency.query.order_by(InstitutionDependency.name).all()

        # Solo mostrar estatus activo e inactivo para filtros
        statuses = Status.query.filter(Status.status_code.in_(['STAT-001', 'STAT-002'])).all()

        # Obtener todos los estados
        states = State.query.order_by(State.name).all()

        # Filtrar parroquias según el usuario
        if user and user.person and user.person.institutional_staff:
            # Obtener el estado del usuario a través de su institución
            user_institution = user.person.institutional_staff[0].institution
            if user_institution and user_institution.parish and user_institution.parish.municipality:
                user_state_id = user_institution.parish.municipality.state_id
                # Si es Distrito Capital, usar lista oficial de parroquias con verificación de estado
                if user_state_id == 24:  # ID de Distrito Capital
                    parishes = Parish.query.join(Municipality).join(State).filter(
                        Parish.name.in_(DC_PARISHES),
                        State.state_code == DC_STATE_CODE
                    ).order_by(Parish.name).all()
                else:
                    # Para otros estados, filtrar por estado
                    parishes = Parish.query.join(Municipality).filter(
                        Municipality.state_id == user_state_id
                    ).order_by(Parish.name).all()
            else:
                parishes = []
        else:
            # Para super admin: parroquias reales de Distrito Capital
            # Filtrar por lista oficial de parroquias de Caracas Y estado para evitar duplicados
            parishes = (
                Parish.query
                .join(Municipality)
                .join(State)
                .filter(
                    Parish.name.in_(DC_PARISHES),
                    State.state_code == DC_STATE_CODE
                )
                .order_by(Parish.name)
                .all()
            )

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
    
    Parámetros:
    - institution_id: ID de la institución a modificar
    
    Retorna:
    - tuple: (institution, new_status) si éxito, (None, error_message) si error
    
    Nota:
    - Realiza commit de cambios en base de datos
    - Realiza rollback en caso de error
    - Si la institución se desactiva, también se desactivan los usuarios afiliados
    - Si la institución se activa, también se activan los usuarios afiliados
    """
    try:
        from app.extensions import db
        from app.models.institutional_staff_model import InstitutionalStaff
        from app.models.user_model import User
        
        institution = db.session.get(Institution, institution_id)
        if not institution:
            return None, 'Institución no encontrada'
        
        # Obtener los estatus Activo e Inactivo
        active_status = Status.query.filter_by(status_code='STAT-001').first()
        inactive_status = Status.query.filter_by(status_code='STAT-002').first()
        
        if not active_status or not inactive_status:
            return None, 'Estados no configurados correctamente'
        
        # Determinar el nuevo estatus de la institución
        if institution.status_id == active_status.id:
            institution.status_id = inactive_status.id
            new_institution_status = inactive_status
            new_status = 'Inactivo'
        else:
            institution.status_id = active_status.id
            new_institution_status = active_status
            new_status = 'Activo'
        
        # Actualizar el estatus de los usuarios afiliados a la institución
        # Obtener todo el personal institucional de esta institución con relaciones cargadas
        from app.models.institutional_staff_model import InstitutionalStaff
        from app.models.person_model import Person
        from app.models.user_model import User
        
        staff_list = InstitutionalStaff.query.options(
            joinedload(InstitutionalStaff.person).joinedload(Person.user).joinedload(User.status)
        ).filter_by(institution_id=institution_id).all()
        
        for staff in staff_list:
            # Verificar si la persona tiene un usuario
            if staff.person and staff.person.user:
                user = staff.person.user
                # Actualizar el estatus del usuario al mismo estatus de la institución
                user.status_id = new_institution_status.id
        
        from app.extensions import db
        db.session.commit()
        
        # Recargar la institución para obtener el estatus actualizado
        db.session.refresh(institution)
        
        return institution, new_status
    except Exception as e:
        print(f"Error en toggle_institution_status: {e}")
        from app.extensions import db
        db.session.rollback()
        return None, f'Error: {str(e)}'

def get_institution_users(institution_id, page=1, per_page=10):
    """
    Obtiene los usuarios afiliados a una institución específica con paginación.
    
    Parámetros:
    - institution_id: ID de la institución
    - page: número de página para paginación
    - per_page: cantidad de registros por página
    
    Retorna:
    - dict: con usuarios paginados y metadatos de paginación
    """
    try:
        from app.models.institutional_staff_model import InstitutionalStaff
        from app.models.person_model import Person
        from app.models.user_model import User
        from app.models.position_model import Position
        from app.models.status_model import Status
        from sqlalchemy.orm import joinedload
        
        # Obtener el personal institucional con todas las relaciones cargadas
        query = InstitutionalStaff.query.options(
            joinedload(InstitutionalStaff.person).joinedload(Person.user),
            joinedload(InstitutionalStaff.position),
            joinedload(InstitutionalStaff.institution)
        ).filter_by(institution_id=institution_id)
        
        # Obtener total de registros para paginación
        total = query.count()
        
        # Aplicar paginación
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        users_data = []
        for staff in pagination.items:
            person = staff.person
            user = person.user if person else None
            
            # Obtener el estatus del usuario si existe
            user_status = None
            if user and user.status:
                user_status = {
                    'status_code': user.status.status_code,
                    'status_name': user.status.status_name
                }
            
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
                'has_user_account': user is not None
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
            'next_num': pagination.next_num
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
            'next_num': None
        }

def validate_institution_data(institution_data, is_admin=False):
    """
    Valida los datos de una institución antes de actualizar.
    
    Parámetros:
    - institution_data: dict con datos de la institución a validar
    - is_admin: booleano que indica si el usuario es administrador
    
    Retorna:
    - tuple: (is_valid, errors) donde is_valid es boolean y errors es dict con errores por campo
    """
    errors = {}
    
    # Validar teléfono (ambos roles)
    if 'phone' in institution_data:
        phone = institution_data['phone']
        if not phone or phone.strip() == '':
            errors['phone'] = 'El teléfono es obligatorio'
        else:
            # Limpiar paréntesis y guiones para validación
            clean_phone = phone.replace('(', '').replace(')', '').replace('-', '').strip()
            # Validar formato: 11 dígitos numéricos
            pattern = r'^\d{11}$'
            if not re.match(pattern, clean_phone):
                errors['phone'] = 'Formato de teléfono inválido. Debe ser (XXXX)-XXXXXXX (ej: (0414)-1234567)'
    
    # Validar dirección (ambos roles)
    if 'address' in institution_data:
        address = institution_data['address']
        if not address or address.strip() == '':
            errors['address'] = 'La dirección es obligatoria'
        elif len(address.strip()) < 5:
            errors['address'] = 'La dirección debe tener al menos 5 caracteres'
        elif len(address.strip()) > 200:
            errors['address'] = 'La dirección no puede exceder 200 caracteres'
    
    # Validaciones solo para administradores
    if is_admin:
        # Validar código de plantel (DEA)
        if 'plantel_code' in institution_data:
            plantel_code = institution_data['plantel_code']
            if not plantel_code or plantel_code.strip() == '':
                errors['plantel_code'] = 'El código de plantel es obligatorio'
            else:
                # Validar formato DEA: XXX-X0000 (ej: DEA-U0001)
                pattern = r'^[A-Z]{3}-[A-Z]{1}[0-9]{4}$'
                if not re.match(pattern, plantel_code.upper()):
                    errors['plantel_code'] = 'Formato de código de plantel inválido. Debe ser XXX-X0000 (ej: DEA-U0001)'
        
        # Validar nombre de institución
        if 'institution_name' in institution_data:
            institution_name = institution_data['institution_name']
            if not institution_name or institution_name.strip() == '':
                errors['institution_name'] = 'El nombre de la institución es obligatorio'
            elif len(institution_name.strip()) < 3:
                errors['institution_name'] = 'El nombre debe tener al menos 3 caracteres'
            elif len(institution_name.strip()) > 100:
                errors['institution_name'] = 'El nombre no puede exceder 100 caracteres'
        
        # Validar tipo de institución
        if 'institution_type_id' in institution_data:
            institution_type_id = institution_data['institution_type_id']
            if not institution_type_id:
                errors['institution_type'] = 'Debe seleccionar un tipo de institución'
            else:
                try:
                    institution_type_id = int(institution_type_id)
                    type_exists = InstitutionType.query.get(institution_type_id)
                    if not type_exists:
                        errors['institution_type'] = 'El tipo de institución seleccionado no existe'
                except (ValueError, TypeError):
                    errors['institution_type'] = 'Tipo de institución inválido'
        
        # Validar alcance de institución
        if 'institution_scope_id' in institution_data:
            institution_scope_id = institution_data['institution_scope_id']
            if not institution_scope_id:
                errors['institution_scope'] = 'Debe seleccionar un alcance de institución'
            else:
                try:
                    institution_scope_id = int(institution_scope_id)
                    scope_exists = InstitutionScope.query.get(institution_scope_id)
                    if not scope_exists:
                        errors['institution_scope'] = 'El alcance de institución seleccionado no existe'
                except (ValueError, TypeError):
                    errors['institution_scope'] = 'Alcance de institución inválido'
        
        # Validar dependencia de institución
        if 'institution_dependency_id' in institution_data:
            institution_dependency_id = institution_data['institution_dependency_id']
            if not institution_dependency_id:
                errors['institution_dependency'] = 'Debe seleccionar una dependencia de institución'
            else:
                try:
                    institution_dependency_id = int(institution_dependency_id)
                    dependency_exists = InstitutionDependency.query.get(institution_dependency_id)
                    if not dependency_exists:
                        errors['institution_dependency'] = 'La dependencia de institución seleccionada no existe'
                except (ValueError, TypeError):
                    errors['institution_dependency'] = 'Dependencia de institución inválida'
        
        # Validar parroquia (ubicación)
        if 'parish_id' in institution_data:
            parish_id = institution_data['parish_id']
            if not parish_id:
                errors['parish_id'] = 'Debe seleccionar una parroquia'
            else:
                try:
                    parish_id = int(parish_id)
                    parish_exists = Parish.query.get(parish_id)
                    if not parish_exists:
                        errors['parish_id'] = 'La parroquia seleccionada no existe'
                except (ValueError, TypeError):
                    errors['parish_id'] = 'Parroquia inválida'
        
        # Validar ciudad (ubicación)
        if 'city_id' in institution_data:
            city_id = institution_data['city_id']
            if not city_id:
                errors['city_id'] = 'Debe seleccionar una ciudad'
            else:
                try:
                    city_id = int(city_id)
                    city_exists = City.query.get(city_id)
                    if not city_exists:
                        errors['city_id'] = 'La ciudad seleccionada no existe'
                except (ValueError, TypeError):
                    errors['city_id'] = 'Ciudad inválida'
    
    return len(errors) == 0, errors

def update_institution_contact_infrastructure(institution_id, institution_data, is_admin=False):
    """
    Actualiza los datos de contacto e infraestructura de una institución.
    Para applicants: solo actualiza teléfono y dirección.
    Para administradores: actualiza todos los campos incluyendo código de plantel y ubicación.
    
    Parámetros:
    - institution_id: ID de la institución a actualizar
    - institution_data: dict con datos de la institución
    - is_admin: booleano que indica si el usuario es administrador
    
    Retorna:
    - tuple: (institution, success, message) si éxito, (None, False, error_message) si error
    
    Nota:
    - Realiza commit de cambios en base de datos
    - Realiza rollback en caso de error
    - Registra la acción en la bitácora
    """
    try:
        from app.extensions import db
        from app.utils.binnacle_utils import log_action
        from flask_login import current_user
        
        # Validar datos antes de procesar según rol
        is_valid, validation_errors = validate_institution_data(institution_data, is_admin)
        if not is_valid:
            return None, False, 'Errores de validación: ' + '; '.join(validation_errors.values())
        
        institution = db.session.get(Institution, institution_id)
        if not institution:
            return None, False, 'Institución no encontrada'
        
        # Guardar valores anteriores para bitácora
        old_values = {
            'phone': institution.phone,
            'address': institution.address
        }
        
        if is_admin:
            # Para administradores, guardar todos los valores anteriores
            old_values.update({
                'plantel_code': institution.plantel_code,
                'institution_name': institution.institution_name,
                'institution_type_id': institution.institution_type_id,
                'institution_scope_id': institution.institution_scope_id,
                'institution_dependency_id': institution.institution_dependency_id,
                'parish_id': institution.parish_id,
                'city_id': None
            })
            
            # Obtener ciudad actual
            if institution.parish and institution.parish.locations and len(institution.parish.locations) > 0:
                old_values['city_id'] = institution.parish.locations[0].city_id
        
        # Actualizar datos según rol
        # Campos que ambos roles pueden editar
        if 'phone' in institution_data:
            # Limpiar el teléfono de paréntesis y guiones antes de guardar
            clean_phone = institution_data['phone'].replace('(', '').replace(')', '').replace('-', '').strip()
            institution.phone = clean_phone
        if 'address' in institution_data:
            institution.address = institution_data['address']
        
        # Campos que solo administradores pueden editar
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
            
            # Manejo de ciudad a través de Location
            if 'city_id' in institution_data and institution_data['city_id']:
                # Eliminar locations existentes para esta parroquia
                Location.query.filter_by(parish_id=institution.parish_id).delete()
                
                # Obtener ciudad y parroquia de forma segura
                city = City.query.get(institution_data['city_id'])
                parish = Parish.query.get(institution.parish_id)
                
                # Crear nueva location solo si ambas existen
                if city and parish:
                    new_location = Location(
                        city_id=institution_data['city_id'],
                        parish_id=institution.parish_id,
                        name=f"{city.name} - {parish.name}"
                    )
                    db.session.add(new_location)
        
        db.session.commit()
        
        # Recargar la institución para obtener los datos actualizados
        db.session.refresh(institution)
        
        # Registrar en bitácora
        try:
            from app.utils.binnacle_utils import log_action
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