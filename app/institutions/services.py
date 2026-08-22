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

def get_user_state_info(user):
    """
    Obtiene la información del estado al que pertenece un usuario administrador.
    
    Esta función centraliza la lógica para determinar el estado de un usuario basándose
    en su relación con la empresa a través de la ruta: User -> Person -> CompanyStaff -> Place -> Parish -> Municipality -> State.
    Utiliza state_code en lugar de IDs numéricos para mayor robustez y mantenimiento.
    
    Parámetros:
    - user: objeto User del usuario actual
    
    Retorna:
    - dict con información del estado:
        - state_id: ID del estado (para queries compatibles)
        - state_code: Código del estado (identificador robusto)
        - state_name: Nombre del estado
    - None si no se puede determinar el estado del usuario
    """
    if not user:
        return None
    
    try:
        from app.models.user_model import User
        from app.models.person_model import Person
        from app.models.company_staff_model import CompanyStaff
        from app.models.place_model import Place
        from app.models.parish_model import Parish
        from app.models.municipality_model import Municipality
        from app.models.state_model import State
        
        # Recargar el usuario con todas las relaciones necesarias usando joinedload
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
        import traceback
        traceback.print_exc()
        return None

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
    - Super admin ve todas las instituciones y puede filtrar por cualquier estado
    - Administradores estadales solo ven instituciones de su estado
    """
    try:
        # Verificar si el usuario es super admin
        is_super_admin = False
        if user and user.roles_assoc:
            for role_assoc in user.roles_assoc:
                if role_assoc.role.name == 'super_admin':
                    is_super_admin = True
                    break
        
        # Obtener información del estado del usuario de forma centralizada (solo para admin estatal)
        user_state_info = None
        if not is_super_admin:
            try:
                user_state_info = get_user_state_info(user)
            except Exception as e:
                print(f"Error obteniendo información del estado: {e}")
                user_state_info = None
        
        # Cargar relaciones optimizadamente para evitar N+1 queries
        query = Institution.query.options(
            joinedload(Institution.institution_type),
            joinedload(Institution.institution_scope),
            joinedload(Institution.institution_dependency),
            joinedload(Institution.parish).joinedload(Parish.municipality).joinedload(Municipality.state),
            joinedload(Institution.status),
            joinedload(Institution.institution_levels).joinedload(InstitutionLevel.educational_level)
        )

        # Aplicar restricciones geográficas según el tipo de usuario
        if user_state_info:
            # Administrador estadal: filtrar por su estado usando state_code
            query = query.join(Parish).join(Municipality).join(State).filter(
                State.state_code == user_state_info['state_code']
            )
        # Super admin: ver todas las instituciones sin restricciones geográficas iniciales
        # Pero los joins se agregarán si se filtra por estado

        # Primero, obtener todos los IDs ordenados sin filtros para calcular índices originales
        base_query = Institution.query
        # Aplicar las mismas restricciones geográficas que la query principal
        if user_state_info:
            base_query = base_query.join(Parish).join(Municipality).join(State).filter(
                State.state_code == user_state_info['state_code']
            )
        
        # Obtener todos los IDs ordenados
        all_ids_query = base_query.order_by(Institution.id.asc())
        all_ids = [institution.id for institution in all_ids_query.all()]
        id_to_index = {id: index + 1 for index, id in enumerate(all_ids)}

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
                # Filtro de estado: solo super admin puede filtrar por estado
                if not user_state_info:
                    # Asegurar que los joins necesarios estén presentes para el filtro de estado
                    query = query.join(Parish).join(Municipality).filter(
                        Municipality.state_id == filters['state_id']
                    )
                # Para admin estatal, ignorar filtro de estado ya que está restringido a su estado
            if filters.get('parish_id'):
                # Filtro de parroquia: para admin estatal, asegurar que sea de su estado
                if user_state_info:
                    # Verificar que la parroquia pertenezca al estado del usuario
                    parish = Parish.query.get(filters['parish_id'])
                    if parish and parish.municipality and parish.municipality.state:
                        if parish.municipality.state.state_code != user_state_info['state_code']:
                            # Si la parroquia no es del estado del usuario, ignorar el filtro
                            pass
                        else:
                            query = query.filter(Institution.parish_id == filters['parish_id'])
                else:
                    # Super admin puede filtrar por cualquier parroquia
                    query = query.filter(Institution.parish_id == filters['parish_id'])

        # Obtener total de registros para paginación
        total = query.count()

        # Aplicar paginación
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # Calcular índices originales para los resultados paginados
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
            'total_all': len(all_ids)  # Total sin filtros
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

        # Verificar si el usuario es super admin
        is_super_admin = False
        if user and user.roles_assoc:
            for role_assoc in user.roles_assoc:
                if role_assoc.role.name == 'super_admin':
                    is_super_admin = True
                    break
        
        # Obtener información del estado del usuario de forma centralizada (solo para admin estatal)
        user_state_info = None
        if not is_super_admin:
            try:
                user_state_info = get_user_state_info(user)
            except Exception as e:
                print(f"Error obteniendo información del estado: {e}")
                user_state_info = None

        # Filtrar estados y parroquias según el tipo de usuario
        if user_state_info:
            # Administrador estadal: solo ver su estado y sus parroquias (sin duplicados por nombre)
            states = [State.query.filter_by(state_code=user_state_info['state_code']).first()]
            # Obtener todas las parroquias del estado
            all_parishes = Parish.query.join(Municipality).join(State).filter(
                State.state_code == user_state_info['state_code']
            ).order_by(Parish.name, Parish.id).all()
            # Eliminar duplicados por nombre usando Python (más seguro que GROUP BY)
            seen_names = set()
            parishes = []
            for parish in all_parishes:
                if parish.name not in seen_names:
                    seen_names.add(parish.name)
                    parishes.append(parish)
        else:
            # Super admin: ver todos los estados y todas las parroquias
            states = State.query.order_by(State.name).all()
            # Obtener todas las parroquias
            all_parishes = Parish.query.order_by(Parish.name, Parish.id).all()
            # Eliminar duplicados por nombre usando Python
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
    
    Parámetros:
    - institution_id: ID de la institución a modificar
    
    Retorna:
    - tuple: (institution, new_status) si éxito, (None, error_message) si error
    
    Nota:
    - Realiza commit de cambios en base de datos
    - Realiza rollback en caso de error
    - Solo modifica el estatus de la institución, no afecta a los usuarios afiliados
    """
    try:
        from app.extensions import db
        
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
            new_status = 'Inactivo'
        else:
            institution.status_id = active_status.id
            new_status = 'Activo'
        
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
        
        # Primero, obtener todos los IDs ordenados sin filtros para calcular índices originales
        base_query = InstitutionalStaff.query.filter_by(institution_id=institution_id)
        all_ids_query = base_query.order_by(InstitutionalStaff.id.asc())
        all_ids = [staff.id for staff in all_ids_query.all()]
        id_to_index = {id: index + 1 for index, id in enumerate(all_ids)}
        
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
            
            # Calcular índice original
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
            'total_all': len(all_ids)  # Total sin filtros
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