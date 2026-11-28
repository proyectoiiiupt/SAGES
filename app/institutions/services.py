"""
Servicios del Módulo de Instituciones
Contiene la lógica de negocio para la gestión de instituciones educativas.
"""
import os
import re
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from app.extensions import db
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
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
from flask import current_app
from app.binnacle.services import BinnacleService
from app.binnacle.types import AuditModule, AuditAction, AuditStatus

ROLE_EDIT_WHITELISTS = {
    'applicant': {'phone', 'address'},
    'state_admin': {
        'phone', 'address', 'institution_name',
        'institution_type_id', 'institution_scope_id', 'institution_dependency_id',
        'educational_levels', 'municipality_id', 'parish_id'
    },
    'super_admin': {
        'phone', 'address', 'institution_name',
        'institution_type_id', 'institution_scope_id', 'institution_dependency_id',
        'educational_levels', 'municipality_id', 'parish_id',
        'state_id', 'plantel_code'
    }
}

ALLOWED_EDUCATIONAL_LEVELS = {
    'INST-001': {'EDUL-005', 'EDUL-006'},  # Universidad
    'INST-002': {'EDUL-005'},              # Instituto Universitario
    'INST-003': {'EDUL-003', 'EDUL-004'},  # Liceo / Educación Media
    'INST-004': {'EDUL-001', 'EDUL-002'},  # Escuela Básica / Primaria
    'INST-006': {'EDUL-001', 'EDUL-002', 'EDUL-003', 'EDUL-004'},  # Complejo Educativo Integral
    'INST-005': set()                      # Centro de Formación Técnica y Laboral
}


def get_city_by_parish_id(parish_id):
    """
    Obtiene la ciudad asociada a una parroquia a través de sages.locations (solo lectura).
    Aspecto inmutable: no se edita la ciudad, solo se consulta.
    """
    if not parish_id:
        return None
    try:
        location = Location.query.filter_by(parish_id=parish_id).first()
        return location.city if location else None
    except Exception as e:
        current_app.logger.error("Error en get_city_by_parish_id", exc_info=True)
        return None


def get_user_state_info(user):
    """
    Obtiene la información del estado al que pertenece un usuario administrador.
    
    User -> Person -> CompanyStaff -> Place -> Parish -> Municipality -> State.
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
        current_app.logger.error("Error en get_user_state_info", exc_info=True)
        return None


def get_all_institutions(filters=None, user=None, page=1, per_page=10):
    """
    Obtiene todas las instituciones con sus relaciones cargadas.
    Aplica filtros opcionales y paginación.
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
                current_app.logger.error("Error obteniendo información del estado en get_all_institutions", exc_info=True)
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

        # Filtrar únicamente instituciones aprobadas (STAT-001 Activo, STAT-002 Inactivo)
        approved_statuses = Status.query.filter(Status.status_code.in_(['STAT-001', 'STAT-002'])).all()
        approved_status_ids = [s.id for s in approved_statuses]

        if approved_status_ids:
            query = query.filter(Institution.status_id.in_(approved_status_ids))
            base_query = base_query.filter(Institution.status_id.in_(approved_status_ids))
        else:
            pending_status = Status.query.filter_by(status_code='STAT-004').first()
            if pending_status:
                query = query.filter(Institution.status_id != pending_status.id)
                base_query = base_query.filter(Institution.status_id != pending_status.id)
        
        all_ids = [r[0] for r in base_query.with_entities(Institution.id).order_by(Institution.id.asc()).all()]
        id_to_index = {id: index + 1 for index, id in enumerate(all_ids)}

        query = query.order_by(Institution.id)

        if filters:
            if filters.get('search_name'):
                search_term = filters['search_name']
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
        current_app.logger.error("Error en get_all_institutions", exc_info=True)
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
    """Obtiene una institución específica por su ID con todas sus relaciones cargadas."""
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
        current_app.logger.error("Error en get_institution_by_id", exc_info=True)
        return None


def get_filter_options(user=None):
    """Obtiene las opciones disponibles para los filtros del listado de instituciones."""
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
                current_app.logger.error("Error obteniendo información del estado en get_all_institutions", exc_info=True)
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
        current_app.logger.error("Error en get_filter_options", exc_info=True)
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
    Al inactivar NO se cambia User.status en cascada: las cuentas quedan activas en modo
    solo lectura. Se bloquea la creación de solicitudes mediante @institution_active_required.
    Se envía 1 solo correo al representante/director de la institución.
    No permite inactivar si la institución tiene solicitudes de formación pendientes (STAT-003, STAT-004), planificadas (STAT-005) o en proceso (STAT-006).
    """
    try:
        institution = db.session.get(Institution, institution_id)
        if not institution:
            return None, 'Institución no encontrada', 0

        active_status = Status.query.filter_by(status_code='STAT-001').first()
        inactive_status = Status.query.filter_by(status_code='STAT-002').first()

        if not active_status or not inactive_status:
            return None, 'Estados no configurados correctamente', 0

        old_status_id = institution.status_id
        old_status_name = 'Activo' if institution.status_id == active_status.id else 'Inactivo'

        if institution.status_id == active_status.id:
            # Verificar si la institución tiene solicitudes de formación pendientes o en proceso
            from app.models.request_model import Request
            pending_statuses = Status.query.filter(
                Status.status_code.in_(['STAT-003', 'STAT-004', 'STAT-005', 'STAT-006'])
            ).all()
            pending_status_ids = [s.id for s in pending_statuses]

            if pending_status_ids:
                pending_requests = (
                    db.session.query(Request)
                    .join(Request.institutional_staff)
                    .filter(
                        InstitutionalStaff.institution_id == institution_id,
                        Request.status_id.in_(pending_status_ids),
                        Request.historical == False
                    )
                    .first()
                )
                if pending_requests:
                    return None, 'No se puede inactivar la institución porque tiene solicitudes de formación pendientes o en proceso.', 0

            institution.status_id = inactive_status.id
            new_status = 'Inactivo'
        else:
            institution.status_id = active_status.id
            new_status = 'Activo'

        # Al inactivar NO se modifica User.status en cascada.
        # Las cuentas permanecen activas en modo solo lectura con banner en Home.
        # La creación de solicitudes se bloquea con @institution_active_required.
        affected_users_count = 0

        institution._skip_auto_audit = True

        BinnacleService.create_log_entry(
            module=AuditModule.INSTITUTIONS.value,
            action_type=AuditAction.CAMBIO_ESTATUS_INSTITUCION.value,
            description=f'Institución {institution.institution_code} cambiada a {new_status}. Cuentas de usuarios afiliados conservadas activas en modo solo lectura (sin cascada).',
            target_table='sages.institutions',
            record_id=institution.id,
            status=AuditStatus.MODIFICADO.value,
            old_values={'status_id': old_status_id, 'status': old_status_name},
            new_values={'status_id': institution.status_id, 'status': new_status}
        )

        db.session.commit()
        db.session.refresh(institution)

        # --- Notificación interna a todos los afiliados ---
        try:
            from app.notifications.services import NotificationService
            from app.notifications.enums import NotificationEvent
            from flask_login import current_user

            modificado_por = "Administración Central"
            if current_user and hasattr(current_user, 'person') and current_user.person:
                modificado_por = f"{current_user.person.first_name} {current_user.person.last_name}".strip()

            event_type = (
                NotificationEvent.INSTITUTION_ACTIVATED
                if new_status == 'Activo'
                else NotificationEvent.INSTITUTION_INACTIVATED
            )
            context = {"institution_name": institution.institution_name}
            if new_status != 'Activo':
                context["_display"] = {
                    "Institución": institution.institution_name,
                    "Suspendido Por": modificado_por
                }
            else:
                context["_display"] = {
                    "Institución": institution.institution_name,
                    "Reactivado Por": modificado_por
                }

            NotificationService.notify_institution_affiliates(
                institution_id=institution.id,
                event=event_type,
                context=context,
                redirect_url="/institutions/my-institution",
                action_text="Ver Detalles"
            )
        except Exception as e:
            current_app.logger.error("Error enviando notificacion de estatus", exc_info=True)

        # --- Correo al representante/director (solo al inactivar, 1 solo correo) ---
        if new_status == 'Inactivo':
            try:
                _send_inactivation_email_to_representative(institution)
            except Exception as e:
                current_app.logger.error("Error enviando correo de inactivación al representante", exc_info=True)

        return institution, new_status, affected_users_count
    except Exception as e:
        current_app.logger.error("Error en toggle_institution_status", exc_info=True)
        db.session.rollback()
        return None, f'Error: {str(e)}', 0


def _send_inactivation_email_to_representative(institution):
    """
    Envía 1 solo correo de notificación de inactivación al representante o director
    principal de la institución (primer staff con cargo POS-001, POS-002 o POS-003,
    o bien el primer staff con cuenta activa si ninguno de esos cargos existe).
    """
    from app.utils.email_utils import send_institution_inactivated_email

    # Cargos representativos prioritarios: Rector, Vicerrector Académico, Director
    priority_codes = ('POS-001', 'POS-002', 'POS-003')

    staff_list = (
        InstitutionalStaff.query
        .options(
            joinedload(InstitutionalStaff.person).joinedload(Person.user),
            joinedload(InstitutionalStaff.position)
        )
        .filter_by(institution_id=institution.id)
        .all()
    )

    # Buscar primero por cargo prioritario
    representative = None
    for code in priority_codes:
        for staff in staff_list:
            if (
                staff.position
                and staff.position.position_code == code
                and staff.person
                and staff.person.email
            ):
                representative = staff
                break
        if representative:
            break

    # Si no hay cargo prioritario, tomar el primer staff con e-mail
    if not representative:
        for staff in staff_list:
            if staff.person and staff.person.email:
                representative = staff
                break

    if not representative:
        print(f"[INFO] Institución {institution.institution_code}: sin representante con correo para notificación de inactivación.")
        return

    person = representative.person
    full_name = f"{person.first_name} {person.last_name}".strip()
    send_institution_inactivated_email(
        to_email=person.email,
        full_name=full_name,
        institution_name=institution.institution_name,
        institution_code=institution.institution_code
    )


def get_institution_users(institution_id, page=1, per_page=10):
    """Obtiene los usuarios afiliados a una institución específica con paginación.
    Solo incluye usuarios con cuenta activa (STAT-001).
    """
    try:
        # Filtrar solo staff con usuario activo (STAT-001) para el índice base
        active_status = Status.query.filter_by(status_code='STAT-001').first()
        active_status_id = active_status.id if active_status else None

        base_query = (
            InstitutionalStaff.query
            .join(Person, InstitutionalStaff.person_id == Person.id)
            .join(User, Person.id == User.person_id)
            .filter(
                InstitutionalStaff.institution_id == institution_id,
                InstitutionalStaff.status_id == active_status_id,
                User.status_id == active_status_id
            )
        )
        all_ids_query = base_query.order_by(InstitutionalStaff.id.asc())
        all_ids = [staff.id for staff in all_ids_query.all()]
        id_to_index = {id: index + 1 for index, id in enumerate(all_ids)}

        query = InstitutionalStaff.query.options(
            joinedload(InstitutionalStaff.person).joinedload(Person.user).joinedload(User.status),
            joinedload(InstitutionalStaff.position)
        ).join(Person, InstitutionalStaff.person_id == Person.id).join(User, Person.id == User.person_id).filter(
            InstitutionalStaff.institution_id == institution_id,
            InstitutionalStaff.status_id == active_status_id,
            User.status_id == active_status_id
        )

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
                'user_id': user.id if user else None,
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
        current_app.logger.error("Error en get_institution_users", exc_info=True)
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


def validate_institution_data(institution_data, is_admin=False, user_role=None, user=None, institution_id=None):
    r"""
    Valida los datos de una institución antes de actualizar según las reglas de negocio y rol:
    - Límites de validación unificados con forms.py:
        * address: min 10, max 500
        * institution_name: min 3, max 200
        * phone: min 7, max 20, regex r'^\+?[\d\s\-]{7,20}$'
        * plantel_code: regex ^[A-Z0-9\-]{4,20}$ y unicidad (solo super_admin)
    - state_admin: valida en servidor que la parroquia pertenezca a su mismo estado (state_id bloqueado).
    - super_admin: puede modificar state_id y plantel_code.
    - educational_levels: valida correspondencia con ALLOWED_EDUCATIONAL_LEVELS según institution_type.
    """
    errors = {}
    
    # 1. Teléfono institucional (opcional, aplicable a todos los roles)
    if 'phone' in institution_data:
        phone = (institution_data['phone'] or '').strip()
        if phone:
            if len(phone) < 7:
                errors['phone'] = 'El teléfono debe tener al menos 7 caracteres'
            elif len(phone) > 20:
                errors['phone'] = 'El teléfono no puede exceder 20 caracteres'
            elif not re.match(r'^\+?[\d\s\-]{7,20}$', phone):
                errors['phone'] = 'Formato de teléfono inválido (ej: 0414-1234567 o +58 212 1234567)'

    # 2. Dirección detallada (min 10, max 500, unificado con forms.py)
    if 'address' in institution_data:
        address = (institution_data['address'] or '').strip()
        if not address:
            errors['address'] = 'La dirección es obligatoria'
        elif len(address) < 10:
            errors['address'] = 'La dirección debe tener al menos 10 caracteres'
        elif len(address) > 500:
            errors['address'] = 'La dirección no puede exceder 500 caracteres'

    # 3. Código del plantel (solo editable por super_admin)
    if 'plantel_code' in institution_data:
        plantel_code = (institution_data['plantel_code'] or '').strip().upper()
        if not plantel_code:
            errors['plantel_code'] = 'El código de plantel es obligatorio'
        elif len(plantel_code) < 4:
            errors['plantel_code'] = 'El código de plantel debe tener al menos 4 caracteres'
        elif len(plantel_code) > 20:
            errors['plantel_code'] = 'El código de plantel no puede exceder 20 caracteres'
        elif not re.match(r'^[A-Z0-9\-]{4,20}$', plantel_code):
            errors['plantel_code'] = 'Formato de código de plantel inválido. Debe contener entre 4 y 20 caracteres (mayúsculas, números y guiones)'
        else:
            # Validación de unicidad
            query = Institution.query.filter(Institution.plantel_code == plantel_code)
            if institution_id:
                query = query.filter(Institution.id != institution_id)
            existing = query.first()
            if existing:
                errors['plantel_code'] = f'El código de plantel "{plantel_code}" ya está registrado por otra institución'

    # 4. Nombre de la institución (min 3, max 200, unificado con forms.py)
    if 'institution_name' in institution_data:
        institution_name = (institution_data['institution_name'] or '').strip()
        if not institution_name:
            errors['institution_name'] = 'El nombre de la institución es obligatorio'
        elif len(institution_name) < 3:
            errors['institution_name'] = 'El nombre debe tener al menos 3 caracteres'
        elif len(institution_name) > 200:
            errors['institution_name'] = 'El nombre no puede exceder 200 caracteres'

    # 5. Tipo de institución
    inst_type_obj = None
    if 'institution_type_id' in institution_data:
        institution_type_id = institution_data['institution_type_id']
        if not institution_type_id:
            errors['institution_type'] = 'Debe seleccionar un tipo de institución'
        else:
            try:
                institution_type_id = int(institution_type_id)
                inst_type_obj = db.session.get(InstitutionType, institution_type_id)
                if not inst_type_obj:
                    errors['institution_type'] = 'El tipo de institución seleccionado no existe'
            except (ValueError, TypeError):
                errors['institution_type'] = 'Tipo de institución inválido'

    # 6. Alcance
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

    # 7. Dependencia
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

    # 8. Niveles Educativos
    if 'educational_levels' in institution_data:
        raw_levels = institution_data['educational_levels']
        if not isinstance(raw_levels, (list, tuple, set)):
            raw_levels = [raw_levels] if raw_levels else []

        if not inst_type_obj and institution_id:
            current_inst = db.session.get(Institution, institution_id)
            if current_inst:
                inst_type_obj = current_inst.institution_type

        type_code = inst_type_obj.institution_type_code if inst_type_obj else None
        allowed_codes = ALLOWED_EDUCATIONAL_LEVELS.get(type_code, set())

        resolved_levels = []
        for item in raw_levels:
            if not item:
                continue
            lvl = None
            if str(item).isdigit():
                lvl = db.session.get(EducationalLevel, int(item))
            else:
                lvl = EducationalLevel.query.filter_by(level_code=str(item).strip()).first()
            if not lvl:
                errors['educational_levels'] = f'Nivel educativo inválido: {item}'
                break
            resolved_levels.append(lvl)

        if 'educational_levels' not in errors:
            invalid = [lvl.name for lvl in resolved_levels if lvl.level_code not in allowed_codes]
            if invalid:
                errors['educational_levels'] = f'Los niveles educativos no corresponden al tipo de institución: {", ".join(invalid)}'
            elif type_code and type_code != 'INST-005' and not resolved_levels:
                errors['educational_levels'] = 'Debe seleccionar al menos un nivel educativo para el tipo de institución seleccionado'

    # 9. Ubicación (Municipio y Parroquia)
    parish_obj = None
    if 'parish_id' in institution_data:
        parish_id = institution_data['parish_id']
        if not parish_id:
            errors['parish_id'] = 'Debe seleccionar una parroquia'
        else:
            try:
                parish_id = int(parish_id)
                parish_obj = db.session.get(Parish, parish_id)
                if not parish_obj:
                    errors['parish_id'] = 'La parroquia seleccionada no existe'
            except (ValueError, TypeError):
                errors['parish_id'] = 'Parroquia inválida'

    municipality_obj = None
    if 'municipality_id' in institution_data:
        municipality_id = institution_data['municipality_id']
        if not municipality_id:
            errors['municipality_id'] = 'Debe seleccionar un municipio'
        else:
            try:
                municipality_id = int(municipality_id)
                municipality_obj = db.session.get(Municipality, municipality_id)
                if not municipality_obj:
                    errors['municipality_id'] = 'El municipio seleccionado no existe'
            except (ValueError, TypeError):
                errors['municipality_id'] = 'Municipio inválido'

    if parish_obj and municipality_obj:
        if parish_obj.municipality_id != municipality_obj.id:
            errors['parish_id'] = 'La parroquia no pertenece al municipio seleccionado'

    # 10. Reglas territoriales por rol
    effective_role = user_role
    if not effective_role and is_admin:
        effective_role = 'super_admin' if (user and any(ra.role.name == 'super_admin' for ra in getattr(user, 'roles_assoc', []))) else 'state_admin'

    if effective_role == 'state_admin':
        # state_admin: validando en servidor que la parroquia pertenezca a su mismo estado (state_id bloqueado)
        user_state_info = get_user_state_info(user)
        if not user_state_info or not user_state_info.get('state_id'):
            errors['state_id'] = 'No se pudo determinar el estado asignado al administrador estadal'
        else:
            admin_state_id = user_state_info['state_id']
            if parish_obj and parish_obj.municipality and parish_obj.municipality.state_id != admin_state_id:
                errors['parish_id'] = 'La parroquia seleccionada no pertenece a su estado asignado'
            if municipality_obj and municipality_obj.state_id != admin_state_id:
                errors['municipality_id'] = 'El municipio seleccionado no pertenece a su estado asignado'
    elif effective_role == 'super_admin':
        # super_admin: puede modificar state_id
        if 'state_id' in institution_data:
            state_id = institution_data['state_id']
            if not state_id:
                errors['state_id'] = 'Debe seleccionar un estado'
            else:
                try:
                    state_id = int(state_id)
                    state_obj = db.session.get(State, state_id)
                    if not state_obj:
                        errors['state_id'] = 'El estado seleccionado no existe'
                    else:
                        if municipality_obj and municipality_obj.state_id != state_obj.id:
                            errors['municipality_id'] = 'El municipio no pertenece al estado seleccionado'
                        if parish_obj and parish_obj.municipality and parish_obj.municipality.state_id != state_obj.id:
                            errors['parish_id'] = 'La parroquia no pertenece al estado seleccionado'
                except (ValueError, TypeError):
                    errors['state_id'] = 'Estado inválido'

    return len(errors) == 0, errors


def update_institution_contact_infrastructure(institution_id, institution_data, is_admin=False, user_role=None, user=None):
    """
    Actualiza los datos de contacto e infraestructura de una institución aplicando:
    - Matriz estricta de edición por rol respaldada por lista blanca en backend.
    - Rol applicant: solo si el plantel está activo (STAT-001), edita phone y address.
    - Rol state_admin: edita phone, address, nombre, clasificación MPPE (tipo, alcance,
      dependencia y niveles educativos) y ubicación (municipio y parroquia de su estado asignado).
    - Rol super_admin: todo lo anterior más state_id y desbloqueo de plantel_code (regex y unicidad).
    - Ciudad es campo informativo inmutable (sin city_id y sin borrado sobre sages.locations).
    """
    try:
        from flask_login import current_user
        effective_user = user or current_user

        # Determinar rol efectivo
        if not user_role:
            if effective_user and hasattr(effective_user, 'roles_assoc') and effective_user.roles_assoc:
                role_names = [ra.role.name for ra in effective_user.roles_assoc]
                if 'super_admin' in role_names:
                    user_role = 'super_admin'
                elif 'state_admin' in role_names:
                    user_role = 'state_admin'
                else:
                    user_role = 'applicant'
            elif is_admin:
                user_role = 'super_admin'
            else:
                user_role = 'applicant'

        institution = db.session.get(Institution, institution_id)
        if not institution:
            return None, False, 'Institución no encontrada'

        # Validación para rol applicant: solo si el plantel está activo (STAT-001)
        if user_role == 'applicant':
            active_status = Status.query.filter_by(status_code='STAT-001').first()
            if not active_status or institution.status_id != active_status.id:
                return None, False, 'La institución se encuentra inactiva. No es posible editar sus datos mientras esté en modo solo lectura.'

        # Aplicar lista blanca estricta por rol
        allowed_fields = ROLE_EDIT_WHITELISTS.get(user_role, {'phone', 'address'})
        filtered_data = {k: v for k, v in institution_data.items() if k in allowed_fields}

        is_valid, validation_errors = validate_institution_data(
            filtered_data,
            is_admin=(user_role in ('state_admin', 'super_admin')),
            user_role=user_role,
            user=effective_user,
            institution_id=institution_id
        )
        if not is_valid:
            return None, False, 'Errores de validación: ' + '; '.join(validation_errors.values())

        # Capturar valores anteriores para auditoría
        old_values = {
            'phone': institution.phone,
            'address': institution.address
        }
        if user_role in ('state_admin', 'super_admin'):
            old_values.update({
                'institution_name': institution.institution_name,
                'institution_type_id': institution.institution_type_id,
                'institution_scope_id': institution.institution_scope_id,
                'institution_dependency_id': institution.institution_dependency_id,
                'parish_id': institution.parish_id,
                'educational_levels': [il.educational_level.name for il in institution.institution_levels if il.educational_level]
            })
        if user_role == 'super_admin':
            old_values['plantel_code'] = institution.plantel_code

        # Aplicar campos de applicant (y roles superiores)
        if 'phone' in filtered_data:
            phone_val = (filtered_data['phone'] or '').strip()
            institution.phone = phone_val if phone_val else None

        if 'address' in filtered_data:
            institution.address = filtered_data['address'].strip()

        # Aplicar campos de state_admin y super_admin
        selected_levels = []
        if user_role in ('state_admin', 'super_admin'):
            if 'institution_name' in filtered_data:
                institution.institution_name = filtered_data['institution_name'].strip()
            if 'institution_type_id' in filtered_data:
                institution.institution_type_id = int(filtered_data['institution_type_id'])
            if 'institution_scope_id' in filtered_data:
                institution.institution_scope_id = int(filtered_data['institution_scope_id'])
            if 'institution_dependency_id' in filtered_data:
                institution.institution_dependency_id = int(filtered_data['institution_dependency_id'])
            if 'parish_id' in filtered_data:
                institution.parish_id = int(filtered_data['parish_id'])

            # Sincronización de niveles educativos (pivote institution_levels)
            if 'educational_levels' in filtered_data:
                raw_levels = filtered_data['educational_levels']
                if not isinstance(raw_levels, (list, tuple, set)):
                    raw_levels = [raw_levels] if raw_levels else []
                for item in raw_levels:
                    if not item:
                        continue
                    if str(item).isdigit():
                        lvl = db.session.get(EducationalLevel, int(item))
                    else:
                        lvl = EducationalLevel.query.filter_by(level_code=str(item).strip()).first()
                    if lvl and lvl not in selected_levels:
                        selected_levels.append(lvl)

                new_level_ids = {lvl.id for lvl in selected_levels}
                # Eliminar los que ya no están
                for il in list(institution.institution_levels):
                    if il.educational_level_id not in new_level_ids:
                        db.session.delete(il)
                # Agregar los nuevos
                current_level_ids = {il.educational_level_id for il in institution.institution_levels}
                for lvl in selected_levels:
                    if lvl.id not in current_level_ids:
                        new_il = InstitutionLevel(institution_id=institution.id, educational_level_id=lvl.id)
                        db.session.add(new_il)

        # Aplicar campos exclusivos de super_admin
        if user_role == 'super_admin':
            if 'plantel_code' in filtered_data and filtered_data['plantel_code']:
                institution.plantel_code = filtered_data['plantel_code'].strip().upper()

        institution._skip_auto_audit = True
        db.session.commit()

        # Auditoría de campos modificados
        changed_fields = {}
        if old_values.get('phone') != institution.phone:
            changed_fields["Teléfono"] = institution.phone or "No registrado"
        if old_values.get('address') != institution.address:
            changed_fields["Dirección"] = institution.address

        if user_role in ('state_admin', 'super_admin'):
            if old_values.get('institution_name') != institution.institution_name:
                changed_fields["Nombre"] = institution.institution_name
            if old_values.get('institution_type_id') != institution.institution_type_id:
                changed_fields["Tipo de Institución"] = institution.institution_type.name if institution.institution_type else "Actualizado"
            if old_values.get('institution_scope_id') != institution.institution_scope_id:
                changed_fields["Alcance"] = institution.institution_scope.name if institution.institution_scope else "Actualizado"
            if old_values.get('institution_dependency_id') != institution.institution_dependency_id:
                changed_fields["Dependencia"] = institution.institution_dependency.name if institution.institution_dependency else "Actualizado"
            if 'educational_levels' in filtered_data:
                old_lvl_set = set(old_values.get('educational_levels', []))
                new_lvl_set = {lvl.name for lvl in selected_levels}
                if old_lvl_set != new_lvl_set:
                    changed_fields["Niveles Educativos"] = ", ".join(lvl.name for lvl in selected_levels) if selected_levels else "Ninguno"
            if old_values.get('parish_id') != institution.parish_id:
                changed_fields["Parroquia"] = institution.parish.name if institution.parish else "Actualizado"
                if institution.parish and institution.parish.municipality:
                    changed_fields["Municipio"] = institution.parish.municipality.name
                    if hasattr(institution.parish.municipality, 'state') and institution.parish.municipality.state:
                        changed_fields["Estado"] = institution.parish.municipality.state.name

        if user_role == 'super_admin':
            if old_values.get('plantel_code') != institution.plantel_code:
                changed_fields["Código de Plantel"] = institution.plantel_code

        # Modificado por
        if effective_user and hasattr(effective_user, 'person') and effective_user.person:
            modificado_por = f"{effective_user.person.first_name} {effective_user.person.last_name}".strip()
        else:
            modificado_por = "Administración Central"
        changed_fields["Modificado Por"] = modificado_por

        new_values = {
            'phone': institution.phone,
            'address': institution.address
        }
        if user_role in ('state_admin', 'super_admin'):
            new_values.update({
                'institution_name': institution.institution_name,
                'institution_type_id': institution.institution_type_id,
                'institution_scope_id': institution.institution_scope_id,
                'institution_dependency_id': institution.institution_dependency_id,
                'parish_id': institution.parish_id,
                'educational_levels': [lvl.name for lvl in selected_levels] if selected_levels else old_values.get('educational_levels', [])
            })
        if user_role == 'super_admin':
            new_values['plantel_code'] = institution.plantel_code

        BinnacleService.create_log_entry(
            module=AuditModule.INSTITUTIONS.value,
            action_type=AuditAction.ACTUALIZAR_INFRAESTRUCTURA.value,
            description=f'Actualización de datos y localización del plantel {institution.plantel_code} efectuada por {modificado_por}',
            target_table='sages.institutions',
            record_id=institution.id,
            status=AuditStatus.MODIFICADO.value,
            old_values=old_values,
            new_values=new_values
        )

        try:
            if len(changed_fields) > 1:
                from app.notifications.services import NotificationService
                from app.notifications.enums import NotificationEvent
                NotificationService.notify_institution_affiliates(
                    institution_id=institution.id,
                    event=NotificationEvent.INSTITUTION_DATA_UPDATED,
                    context={
                        "institution_name": institution.institution_name,
                        "_display": changed_fields
                    },
                    redirect_url="/institutions/my-institution",
                    action_text="Ver Detalles"
                )
        except Exception as e:
            current_app.logger.error("Error enviando notificacion de edicion institucional", exc_info=True)

        db.session.refresh(institution)
        return institution, True, 'Datos actualizados exitosamente'
    except Exception as e:
        current_app.logger.error("Error en update_institution_contact_infrastructure", exc_info=True)
        db.session.rollback()
        return None, False, f'Error al actualizar: {str(e)}'


def create_institution_invitation(institution_id, invited_by_user, email, identification_number, position_id):
    """Crea una invitación para un colaborador de la institución del solicitante."""
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
    ruta_interna = url_for('pre_registration.delegated_register', token=token)
    link = f"{base_url.rstrip('/')}{ruta_interna}"

    # Envío del correo y validación estricta de éxito
    sent = send_invitation_email(email, link, institution.institution_name)
    if not sent:
        raise RuntimeError('No se pudo enviar el correo de invitación. Verifique las credenciales SMTP en el archivo .env.')

    return token