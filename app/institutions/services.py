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
from sqlalchemy.orm import joinedload
from sqlalchemy import or_

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
    - tuple: (institution, new_status, affected_users_count) si éxito, (None, error_message, 0) si error
    
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
            return None, 'Institución no encontrada', 0
        
        # Obtener los estatus Activo e Inactivo
        active_status = Status.query.filter_by(status_code='STAT-001').first()
        inactive_status = Status.query.filter_by(status_code='STAT-002').first()
        
        if not active_status or not inactive_status:
            return None, 'Estados no configurados correctamente', 0
        
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
        
        affected_users_count = 0
        for staff in staff_list:
            # Verificar si la persona tiene un usuario
            if staff.person and staff.person.user:
                user = staff.person.user
                # Actualizar el estatus del usuario al mismo estatus de la institución
                user.status_id = new_institution_status.id
                affected_users_count += 1
        
        from app.extensions import db
        db.session.commit()
        
        # Recargar la institución para obtener el estatus actualizado
        db.session.refresh(institution)
        
        return institution, new_status, affected_users_count
    except Exception as e:
        print(f"Error en toggle_institution_status: {e}")
        from app.extensions import db
        db.session.rollback()
        return None, f'Error: {str(e)}', 0

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