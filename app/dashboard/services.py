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

def get_audit_logs(limit=None):
    """
    Estructura de datos simulada para maquetar la vista de bitácora (US-25).
    Pendiente conectar con la BD en la historia de backend.
    """
    # Dejamos la lista vacía para limpiar la tabla en el frontend
    mock_logs = []
    
    return mock_logs[:limit] if limit else mock_logs

# ─────────────────────────────────────────────────────────────
# BLOQUE MAPA GEOGRÁFICO NACIONAL (Exclusivo super_admin)
# ─────────────────────────────────────────────────────────────

def get_map_states_distribution():
    """
    Calcula los totales de solicitudes y el semáforo operativo para
    todos los estados de Venezuela (Nivel Nacional).
    """
    try:
        # Obtener todos los estados registrados en BD (26 entidades)
        all_states = State.query.order_by(State.id).all()
        
        # Consulta agregada de solicitudes agrupada por estado
        agg_query = db.session.query(
            State.id.label('state_id'),
            func.count(case((Status.status_code == 'STAT-003', Request.id))).label('red_new'),
            func.count(case((Status.status_code.in_(['STAT-004', 'STAT-005', 'STAT-006']), Request.id))).label('yellow_in_progress'),
            func.count(case((Status.status_code == 'STAT-007', Request.id))).label('green_completed'),
            func.count(case((Status.status_code.in_(['STAT-008', 'STAT-009']), Request.id))).label('gray_closed'),
            func.count(Request.id).label('total')
        ).join(Request.status)\
         .join(Request.institutional_staff)\
         .join(InstitutionalStaff.institution)\
         .join(Institution.parish)\
         .join(Parish.municipality)\
         .join(Municipality.state)\
         .group_by(State.id).all()
        
        metrics_by_state = {r.state_id: r for r in agg_query}
        
        states_data = []
        national_totals = {
            'red_new': 0,
            'yellow_in_progress': 0,
            'green_completed': 0,
            'gray_closed': 0,
            'total': 0
        }
        
        for state in all_states:
            m = metrics_by_state.get(state.id)
            red = int(m.red_new) if m else 0
            yellow = int(m.yellow_in_progress) if m else 0
            green = int(m.green_completed) if m else 0
            gray = int(m.gray_closed) if m else 0
            total = int(m.total) if m else 0
            
            # Acumular totales nacionales
            national_totals['red_new'] += red
            national_totals['yellow_in_progress'] += yellow
            national_totals['green_completed'] += green
            national_totals['gray_closed'] += gray
            national_totals['total'] += total
            
            # Determinación de color semafórico predominante
            # Prioridad operativa: Rojo > Amarillo > Verde > Gris
            if red > 0:
                predominant_color = 'red'
            elif yellow > 0:
                predominant_color = 'yellow'
            elif green > 0:
                predominant_color = 'green'
            else:
                predominant_color = 'gray'
            
            # Tasa de resolución estadal
            resolution_rate = round((green / total) * 100) if total > 0 else 0
            
            states_data.append({
                'state_id': state.id,
                'state_code': state.state_code,
                'name': state.name,
                'red_new': red,
                'yellow_in_progress': yellow,
                'green_completed': green,
                'gray_closed': gray,
                'total': total,
                'resolution_rate': resolution_rate,
                'predominant_color': predominant_color
            })
            
        return {
            'states': states_data,
            'summary': national_totals
        }
        
    except Exception as e:
        print(f"Error al calcular distribución del mapa nacional: {e}")
        return {
            'states': [],
            'summary': {
                'red_new': 0,
                'yellow_in_progress': 0,
                'green_completed': 0,
                'gray_closed': 0,
                'total': 0
            }
        }


def get_state_demand_details(state_id: int):
    """
    Obtiene el detalle de demanda y actividad para un estado seleccionado.
    """
    from app.models.training_model import Training
    
    try:
        state = db.session.get(State, state_id)
        if not state:
            return None
            
        # 1. Métricas del semáforo para el estado
        state_metrics_row = db.session.query(
            func.count(case((Status.status_code == 'STAT-003', Request.id))).label('red_new'),
            func.count(case((Status.status_code.in_(['STAT-004', 'STAT-005', 'STAT-006']), Request.id))).label('yellow_in_progress'),
            func.count(case((Status.status_code == 'STAT-007', Request.id))).label('green_completed'),
            func.count(case((Status.status_code.in_(['STAT-008', 'STAT-009']), Request.id))).label('gray_closed'),
            func.count(Request.id).label('total')
        ).join(Request.status)\
         .join(Request.institutional_staff)\
         .join(InstitutionalStaff.institution)\
         .join(Institution.parish)\
         .join(Parish.municipality)\
         .filter(Municipality.state_id == state_id).first()
        
        red = int(state_metrics_row.red_new) if state_metrics_row and state_metrics_row.red_new else 0
        yellow = int(state_metrics_row.yellow_in_progress) if state_metrics_row and state_metrics_row.yellow_in_progress else 0
        green = int(state_metrics_row.green_completed) if state_metrics_row and state_metrics_row.green_completed else 0
        gray = int(state_metrics_row.gray_closed) if state_metrics_row and state_metrics_row.gray_closed else 0
        total = int(state_metrics_row.total) if state_metrics_row and state_metrics_row.total else 0
        resolution_rate = round((green / total) * 100) if total > 0 else 0
        
        # 2. Top 3 Formaciones más solicitadas
        top_trainings = db.session.query(
            Training.name,
            Training.training_code,
            func.count(Request.id).label('count')
        ).select_from(Request)\
         .join(Request.training)\
         .join(Request.institutional_staff)\
         .join(InstitutionalStaff.institution)\
         .join(Institution.parish)\
         .join(Parish.municipality)\
         .filter(Municipality.state_id == state_id)\
         .group_by(Training.name, Training.training_code)\
         .order_by(func.count(Request.id).desc())\
         .limit(3).all()
        
        # 3. Últimas 5 Solicitudes registradas
        recent_requests = db.session.query(
            Request.id,
            Request.request_code,
            Request.created_at,
            Status.status_code,
            Status.status_name,
            Institution.institution_name,
            Training.name.label('training_name')
        ).select_from(Request)\
         .join(Request.status)\
         .join(Request.training)\
         .join(Request.institutional_staff)\
         .join(InstitutionalStaff.institution)\
         .join(Institution.parish)\
         .join(Parish.municipality)\
         .filter(Municipality.state_id == state_id)\
         .order_by(Request.id.desc())\
         .limit(5).all()
        
        return {
            'state': {
                'id': state.id,
                'name': state.name,
                'state_code': state.state_code
            },
            'breakdown': {
                'red_new': red,
                'yellow_in_progress': yellow,
                'green_completed': green,
                'gray_closed': gray,
                'total': total,
                'resolution_rate': resolution_rate
            },
            'top_trainings': [
                {
                    'name': t.name,
                    'code': t.training_code,
                    'count': int(t.count)
                }
                for t in top_trainings
            ],
            'recent_requests': [
                {
                    'id': r.id,
                    'request_code': r.request_code,
                    'status_code': r.status_code,
                    'status_name': r.status_name,
                    'institution_name': r.institution_name,
                    'training_name': r.training_name,
                    'created_at': r.created_at.strftime('%d/%m/%Y %H:%M') if r.created_at else ''
                }
                for r in recent_requests
            ]
        }
        
    except Exception as e:
        print(f"Error al obtener detalle de demanda para estado {state_id}: {e}")
        return None