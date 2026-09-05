"""
Servicios del Módulo de Dashboard (Panel Administrativo)
Contiene la lógica de cálculo y agregación automatizada de indicadores y métricas de solicitudes y usuarios.
"""
from app.extensions import db
from app.models.request_model import Request
from app.models.status_model import Status
from app.models.user_model import User
from app.models.person_model import Person
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.institution_model import Institution
from app.models.parish_model import Parish
from app.models.municipality_model import Municipality
from app.models.state_model import State
from app.models.company_staff_model import CompanyStaff
from app.models.place_model import Place
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case


def get_user_state_info(user):
    """
    Obtiene la información del estado al que pertenece un usuario administrador.
    Ruta: User -> Person -> CompanyStaff -> Place -> Parish -> Municipality -> State.
    """
    if not user:
        return None
    
    try:
        user_with_relations = User.query.options(
            joinedload(User.person)
            .joinedload(Person.company_staff)
            .joinedload(CompanyStaff.place)
            .joinedload(Place.parish)
            .joinedload(Parish.municipality)
            .joinedload(Municipality.state)
        ).filter(User.id == user.id).first()
        
        if (user_with_relations and 
            user_with_relations.person and 
            user_with_relations.person.company_staff):
            
            for staff in user_with_relations.person.company_staff:
                if staff.place and staff.place.parish and staff.place.parish.municipality and staff.place.parish.municipality.state:
                    state = staff.place.parish.municipality.state
                    return {
                        'state_id': state.id,
                        'state_code': state.state_code,
                        'state_name': state.name
                    }
        return None
    except Exception as e:
        print(f"Error al obtener estado del usuario: {e}")
        return None


def get_dashboard_indicators(user):
    """
    Calcula los indicadores métricos automatizados del Dashboard según la jurisdicción del usuario:
    - Total de Solicitudes
    - Usuarios Activos
    - Tasa de Resolución (% completadas / total)
    - Solicitudes Pendientes
    - Solicitudes Atendidas / Completadas
    - Desglose por jurisdicción (atendidas y pendientes)
    """
    # 1. Determinar el rol y la jurisdicción
    is_super_admin = False
    if user and user.roles_assoc:
        for role_assoc in user.roles_assoc:
            if role_assoc.role and role_assoc.role.name == 'super_admin':
                is_super_admin = True
                break

    user_state_info = None
    if not is_super_admin:
        user_state_info = get_user_state_info(user)

    state_id = user_state_info['state_id'] if user_state_info else None
    jurisdiction_label = "Nacional (Todos los Estados)" if is_super_admin else (
        f"Estado {user_state_info['state_name']}" if user_state_info else "Jurisdicción Asignada"
    )

    try:
        # 2. Consultar Solicitudes con sus relaciones geográficas y de estatus
        req_query = db.session.query(
            Request.id,
            Status.status_code,
            Status.status_name,
            State.id.label('state_id'),
            State.name.label('state_name')
        ).join(Request.status)\
         .join(Request.institutional_staff)\
         .join(InstitutionalStaff.institution)\
         .join(Institution.parish)\
         .join(Parish.municipality)\
         .join(Municipality.state)

        if state_id:
            req_query = req_query.filter(State.id == state_id)

        all_requests = req_query.all()
        total_requests = len(all_requests)

        # Códigos de estatus para atención y pendientes
        # STAT-007: Completado (Atendida)
        # STAT-004: Pendiente
        # STAT-003: Nuevo
        # STAT-006: En proceso
        # STAT-005: Planificada
        completed_count = 0
        pending_count = 0
        in_process_count = 0
        new_count = 0
        planned_count = 0

        # Agrupación por estado para el resumen de jurisdicción
        state_distribution = {}

        for req in all_requests:
            code = req.status_code
            s_name = req.state_name

            if s_name not in state_distribution:
                state_distribution[s_name] = {
                    'state_name': s_name,
                    'total': 0,
                    'attended': 0,
                    'pending': 0,
                    'in_process': 0
                }
            state_distribution[s_name]['total'] += 1

            if code == 'STAT-007':
                completed_count += 1
                state_distribution[s_name]['attended'] += 1
            elif code == 'STAT-004':
                pending_count += 1
                state_distribution[s_name]['pending'] += 1
            elif code == 'STAT-006':
                in_process_count += 1
                state_distribution[s_name]['in_process'] += 1
            elif code == 'STAT-003':
                new_count += 1
                state_distribution[s_name]['pending'] += 1
            elif code == 'STAT-005':
                planned_count += 1

        # Tasa de Resolución (Completadas / Total)
        if total_requests > 0:
            resolution_rate = round((completed_count / total_requests) * 100)
        else:
            resolution_rate = 0

        # Solicitudes atendidas totales (completadas)
        attended_requests = completed_count

        # Total de solicitudes pendientes (Pendientes + Nuevas)
        total_pending = pending_count + new_count

        # 3. Usuarios Activos (STAT-001)
        active_status = Status.query.filter_by(status_code='STAT-001').first()
        active_status_id = active_status.id if active_status else 1

        if is_super_admin or not state_id:
            active_users_count = User.query.filter_by(status_id=active_status_id).count()
        else:
            # Usuarios institucionales activos en el estado
            inst_users = db.session.query(User.id)\
                .join(User.person)\
                .join(Person.institutional_staff)\
                .join(InstitutionalStaff.institution)\
                .join(Institution.parish)\
                .join(Parish.municipality)\
                .filter(User.status_id == active_status_id)\
                .filter(Municipality.state_id == state_id)
            
            # Usuarios de empresa activos en el estado
            comp_users = db.session.query(User.id)\
                .join(User.person)\
                .join(Person.company_staff)\
                .join(CompanyStaff.place)\
                .join(Place.parish)\
                .join(Parish.municipality)\
                .filter(User.status_id == active_status_id)\
                .filter(Municipality.state_id == state_id)

            combined_users = inst_users.union(comp_users)
            active_users_count = combined_users.count()

            # Si no hay usuarios específicos mapeados por localidad, mostrar los usuarios activos del sistema
            if active_users_count == 0:
                active_users_count = User.query.filter_by(status_id=active_status_id).count()

        # Convertir distribución geográfica a lista ordenada
        jurisdiction_list = sorted(list(state_distribution.values()), key=lambda x: x['total'], reverse=True)

        return {
            'total_requests': total_requests,
            'active_users': active_users_count,
            'resolution_rate': resolution_rate,
            'pending_requests': total_pending,
            'attended_requests': attended_requests,
            'in_process_requests': in_process_count,
            'planned_requests': planned_count,
            'jurisdiction_label': jurisdiction_label,
            'is_super_admin': is_super_admin,
            'user_state': user_state_info,
            'jurisdiction_summary': jurisdiction_list
        }

    except Exception as e:
        print(f"Error al calcular indicadores del dashboard: {e}")
        # Valores por defecto seguros ante cualquier excepción
        return {
            'total_requests': 0,
            'active_users': 0,
            'resolution_rate': 0,
            'pending_requests': 0,
            'attended_requests': 0,
            'in_process_requests': 0,
            'planned_requests': 0,
            'jurisdiction_label': jurisdiction_label,
            'is_super_admin': is_super_admin,
            'user_state': user_state_info,
            'jurisdiction_summary': []
        }
