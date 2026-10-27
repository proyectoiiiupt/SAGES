"""
Capa de Servicios del Módulo de Configuraciones Globales (SAGES)
Tarea: US-56-places-management
Lógica de negocio para gestión de sedes: generación de código correlativo,
creación, edición y alternancia de estatus con control de integridad referencial.
"""
import logging
import re
from flask import request as flask_request
from app.extensions import db
from app.models.place_model import Place
from app.models.company_model import Company
from app.models.company_staff_model import CompanyStaff
from app.models.status_model import Status
from app.models.municipality_model import Municipality
from app.models.parish_model import Parish
from app.models.state_model import State
from app.models.role_model import Role
from app.models.permission_model import Permission
from app.models.permission_role_model import PermissionRole
from sqlalchemy.orm import joinedload
from app.binnacle.services import BinnacleService
from app.binnacle.types import AuditModule, AuditAction, AuditStatus

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────────────────────────────────────

def _get_active_status():
    """Retorna el objeto Status STAT-001 (Activo). Nunca hardcodea el id."""
    return Status.query.filter_by(status_code='STAT-001').first()


def _get_inactive_status():
    """Retorna el objeto Status STAT-002 (Inactivo). Nunca hardcodea el id."""
    return Status.query.filter_by(status_code='STAT-002').first()


def _get_corpoelec():
    """Retorna la empresa CORPOELEC. Lanza 404 si no existe en la BD."""
    return Company.query.filter_by(company_code='COMP-001').first_or_404()


# ─────────────────────────────────────────────────────────────────────────────
# GENERADOR DE CÓDIGO CORRELATIVO
# ─────────────────────────────────────────────────────────────────────────────

def generate_place_code() -> str:
    """
    Genera el siguiente código correlativo de sede con formato PLC-XXX.
    Consulta todos los códigos existentes con prefijo 'PLC-', extrae el
    valor numérico máximo y retorna el siguiente con relleno de 3 dígitos.
    
    Returns:
        str: Código único, ej. 'PLC-003'.
    """
    existing_codes = db.session.query(Place.place_code).filter(
        Place.place_code.like('PLC-%')
    ).all()

    max_num = 0
    for (code,) in existing_codes:
        match = re.match(r'^PLC-(\d+)$', code)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    return f'PLC-{(max_num + 1):03d}'


# ─────────────────────────────────────────────────────────────────────────────
# SERVICIO DE CREACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def create_place(form_data: dict, user_id: int):
    """
    Registra una nueva sede operativa en sages.places.

    Pasos:
        1. Obtiene la empresa CORPOELEC (COMP-001).
        2. Genera el código correlativo PLC-XXX.
        3. Asigna el estatus inicial Activo (STAT-001).
        4. Persiste el registro en BD.
        5. Registra la acción en sages.binnacle.

    Args:
        form_data (dict): Datos validados del PlaceForm.
        user_id   (int):  ID del usuario autenticado que realiza la operación.

    Returns:
        Place: Instancia persistida de la nueva sede.

    Raises:
        Exception: Propaga cualquier error de BD al controlador.
    """
    try:
        corpoelec   = _get_corpoelec()
        place_code  = generate_place_code()
        status_act  = _get_active_status()

        new_place = Place(
            company_id  = corpoelec.id,
            place_code  = place_code,
            name        = form_data['name'].strip(),
            parish_id   = int(form_data['parish_id']),
            address     = form_data['address'].strip(),
            phone       = form_data['phone'].strip(),
            status_id   = status_act.id
        )
        db.session.add(new_place)
        db.session.flush()   # obtener new_place.id antes del commit

        BinnacleService.create_log_entry(
            module       = AuditModule.CONFIGURATIONS.value,
            action_type  = AuditAction.REGISTRO_NUEVO.value,
            description  = f'Sede registrada: {new_place.name} ({new_place.place_code})',
            status       = AuditStatus.COMPLETADO.value,
            target_table = 'sages.places',
            record_id    = new_place.id,
            new_values   = {
                'place_code': place_code,
                'name'      : new_place.name,
                'parish_id' : new_place.parish_id,
                'address'   : new_place.address,
                'phone'     : new_place.phone,
                'status'    : 'STAT-001'
            }
        )

        db.session.commit()
        logger.info(f'[US-56] Sede creada: {place_code} por user_id={user_id}')
        return new_place

    except Exception as e:
        db.session.rollback()
        logger.error(f'[US-56] Error al crear sede: {str(e)}')
        raise


# ─────────────────────────────────────────────────────────────────────────────
# SERVICIO DE EDICIÓN
# ─────────────────────────────────────────────────────────────────────────────

def update_place(place_id: int, form_data: dict, user_id: int):
    """
    Actualiza los datos de una sede existente.

    Campos actualizables: nombre, parish_id, dirección, teléfono.
    El código (place_code) y la empresa (company_id) son inmutables.

    Args:
        place_id  (int):  ID de la sede a editar.
        form_data (dict): Datos validados del PlaceForm.
        user_id   (int):  ID del usuario autenticado.

    Returns:
        Place: Instancia actualizada.

    Raises:
        404: Si la sede no existe.
        Exception: Propaga errores de BD al controlador.
    """
    try:
        place = Place.query.get_or_404(place_id)

        # Capturar valores anteriores para auditoría JSONB
        old_values = {
            'name'     : place.name,
            'parish_id': place.parish_id,
            'address'  : place.address,
            'phone'    : place.phone
        }

        # Aplicar cambios
        place.name      = form_data['name'].strip()
        place.parish_id = int(form_data['parish_id'])
        place.address   = form_data['address'].strip()
        place.phone     = form_data['phone'].strip()

        new_values = {
            'name'     : place.name,
            'parish_id': place.parish_id,
            'address'  : place.address,
            'phone'    : place.phone
        }

        BinnacleService.create_log_entry(
            module       = AuditModule.CONFIGURATIONS.value,
            action_type  = AuditAction.ACTUALIZAR.value,
            description  = f'Sede actualizada: {place.name} ({place.place_code})',
            status       = AuditStatus.MODIFICADO.value,
            target_table = 'sages.places',
            record_id    = place.id,
            old_values   = old_values,
            new_values   = new_values
        )

        db.session.commit()
        logger.info(f'[US-56] Sede actualizada: {place.place_code} por user_id={user_id}')
        return place

    except Exception as e:
        db.session.rollback()
        logger.error(f'[US-56] Error al actualizar sede {place_id}: {str(e)}')
        raise


# ─────────────────────────────────────────────────────────────────────────────
# SERVICIO DE ALTERNANCIA DE ESTATUS (con control de integridad referencial)
# ─────────────────────────────────────────────────────────────────────────────

def toggle_place_status(place_id: int, user_id: int) -> tuple:
    """
    Alterna el estatus operativo de una sede entre Activo e Inactivo.

    Regla de integridad referencial (Anti-Orfandad):
        Si la sede está Activa y se solicita inactivarla, se verifica que no
        existan funcionarios activos en sages.company_staff adscritos a ella.
        Si los hay, la operación es ABORTADA y se retorna un error descriptivo
        sin alterar la base de datos.

    La reactivación (Inactivo → Activo) no tiene restricciones.
    Nunca se ejecutan sentencias DELETE.

    Args:
        place_id (int): ID de la sede.
        user_id  (int): ID del usuario autenticado.

    Returns:
        tuple: (success: bool, message: str, staff_count: int)
            - (True,  "Sede inactivada correctamente.", 0)
            - (True,  "Sede activada correctamente.",   0)
            - (False, "No es posible inactivar...",     N)
    """
    try:
        place       = Place.query.get_or_404(place_id)
        status_act  = _get_active_status()
        status_ina  = _get_inactive_status()

        # ── Lógica de restricción: solo aplica al intentar INACTIVAR ────────
        if place.status_id == status_act.id:
            active_staff_count = CompanyStaff.query.filter_by(
                place_id  = place_id,
                status_id = status_act.id
            ).count()

            if active_staff_count > 0:
                logger.warning(
                    f'[US-56] Bloqueo integridad referencial: sede {place_id} '
                    f'tiene {active_staff_count} funcionario(s) activo(s).'
                )
                return (
                    False,
                    f'No es posible inactivar la sede "{place.name}" porque tiene '
                    f'{active_staff_count} funcionario(s) administrativo(s) activo(s) adscrito(s). '
                    f'Debe reasignar o inactivar al personal antes de continuar.',
                    active_staff_count
                )

            # Sin funcionarios activos: proceder con la inactivación
            old_status   = 'STAT-001'
            new_status   = 'STAT-002'
            place.status_id = status_ina.id
            action_desc  = f'Sede inactivada: {place.name} ({place.place_code})'
            return_msg   = f'La sede "{place.name}" ha sido inactivada correctamente.'

        else:
            # Reactivación sin restricciones
            old_status   = 'STAT-002'
            new_status   = 'STAT-001'
            place.status_id = status_act.id
            action_desc  = f'Sede activada: {place.name} ({place.place_code})'
            return_msg   = f'La sede "{place.name}" ha sido activada correctamente.'

        BinnacleService.create_log_entry(
            module       = AuditModule.CONFIGURATIONS.value,
            action_type  = AuditAction.CAMBIO_ESTATUS.value,
            description  = action_desc,
            status       = AuditStatus.COMPLETADO.value,
            target_table = 'sages.places',
            record_id    = place.id,
            old_values   = {'status': old_status},
            new_values   = {'status': new_status}
        )

        db.session.commit()
        logger.info(f'[US-56] Estatus cambiado sede {place_id}: {old_status} → {new_status} por user_id={user_id}')
        return (True, return_msg, 0)

    except Exception as e:
        db.session.rollback()
        logger.error(f'[US-56] Error al alternar estatus de sede {place_id}: {str(e)}')
        raise


# ─────────────────────────────────────────────────────────────────────────────
# APIs GEOGRÁFICAS (datos para selectores en cascada)
# ─────────────────────────────────────────────────────────────────────────────

def get_municipalities_by_state(state_id: int) -> list:
    """
    Retorna la lista de municipios de un estado dado, ordenados por nombre.

    Args:
        state_id (int): ID del estado en sages.states.

    Returns:
        list[dict]: [{'id': int, 'name': str}, ...]
    """
    municipalities = (
        Municipality.query
        .filter_by(state_id=state_id)
        .order_by(Municipality.name)
        .all()
    )
    return [{'id': m.id, 'name': m.name} for m in municipalities]


def get_parishes_by_municipality(municipality_id: int) -> list:
    """
    Retorna la lista de parroquias de un municipio dado, ordenadas por nombre.

    Args:
        municipality_id (int): ID del municipio en sages.municipalities.

    Returns:
        list[dict]: [{'id': int, 'name': str}, ...]
    """
    parishes = (
        Parish.query
        .filter_by(municipality_id=municipality_id)
        .order_by(Parish.name)
        .all()
    )
    return [{'id': p.id, 'name': p.name} for p in parishes]


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE SEDES (para la vista principal)
# ─────────────────────────────────────────────────────────────────────────────

def get_places_with_staff_count(page: int = 1, per_page: int = 10):
    """
    Obtiene las sedes de CORPOELEC paginadas con sus relaciones geográficas
    y el conteo de personal administrativo activo adscrito.

    Solo enriquece con staff_count los registros de la página actual para
    evitar N+1 queries sobre toda la tabla.

    Args:
        page     (int): Página actual (1-indexada). Default: 1.
        per_page (int): Registros por página. Default: 10.

    Returns:
        Pagination: Objeto de paginación de Flask-SQLAlchemy con atributo
                    virtual `staff_count` en cada item de la página.
    """
    corpoelec = Company.query.filter_by(company_code='COMP-001').first()
    if not corpoelec:
        return None

    status_act = _get_active_status()

    pagination = (
        Place.query
        .options(
            joinedload(Place.parish)
                .joinedload(Parish.municipality)
                .joinedload(Municipality.state),
            joinedload(Place.status)
        )
        .filter_by(company_id=corpoelec.id)
        .order_by(Place.place_code)
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    # Enriquecer solo los registros de la página actual
    for place in pagination.items:
        place.staff_count = CompanyStaff.query.filter_by(
            place_id  = place.id,
            status_id = status_act.id
        ).count()

    return pagination


# ─────────────────────────────────────────────────────────────────────────────
# SERVICIO DE GESTIÓN DE ROLES Y PERMISOS (RBAC) - US-54 / US-57
# ─────────────────────────────────────────────────────────────────────────────

PROTECTED_SUPER_ADMIN_VIEWS = {
    'view_home',
    'view_admin_panel',
    'manage_users',
    'system_configuration'
}


def get_role_permissions(role_id: int) -> dict:
    """
    Retorna los identificadores de permisos asignados a un rol específico.

    Args:
        role_id (int): Identificador del rol.

    Returns:
        dict: Información del rol y lista de IDs de permisos asignados.
    """
    role = Role.query.get_or_404(role_id)
    assigned_ids = [pr.permission_id for pr in role.permissions_assoc]
    return {
        'role_id': role.id,
        'role_code': role.role_code,
        'role_name': role.name,
        'permission_ids': assigned_ids
    }


def get_all_roles_matrix() -> list:
    """
    Retorna la lista de roles del sistema junto a sus IDs de permisos asignados
    y el conteo de usuarios vinculados, ordenados por id.

    Returns:
        list[dict]: Estructura lista para renderizar la matriz en el frontend.
    """
    roles = Role.query.order_by(Role.id).all()
    matrix = []
    for r in roles:
        matrix.append({
            'id': r.id,
            'role_code': r.role_code,
            'name': r.name,
            'description': r.description,
            'permission_ids': [pr.permission_id for pr in r.permissions_assoc],
            'users_count': len(r.users_assoc)
        })
    return matrix


def update_role_permissions(role_id: int, submitted_permission_ids: list, current_user_id: int) -> dict:
    """
    Sincroniza atómicamente los privilegios asignados a un rol en sages.permissions_roles.

    Aplica la Regla de Integridad Anti-Lockout para garantizar que el rol super_admin
    nunca pierda el acceso a sus vistas críticas.
    Registra la auditoría forense con los deltas exactos en sages.binnacle.

    Args:
        role_id (int): ID del rol en sages.roles.
        submitted_permission_ids (list): Lista de IDs de permisos solicitados por el cliente.
        current_user_id (int): ID del usuario que ejecuta la mutación.

    Returns:
        dict: Resumen de la operación con conteos y deltas.

    Raises:
        ValueError: Si el rol no existe o los datos son inválidos.
        Exception: Error de base de datos con rollback automático.
    """
    try:
        role = Role.query.get(role_id)
        if not role:
            raise ValueError(f"El rol con ID {role_id} no existe en el sistema.")

        # 1. Verificación de permisos válidos (descartar IDs inexistentes o manipulados)
        clean_submitted_ids = []
        for pid in submitted_permission_ids:
            try:
                clean_submitted_ids.append(int(pid))
            except (ValueError, TypeError):
                continue

        valid_permissions = Permission.query.filter(Permission.id.in_(clean_submitted_ids)).all() if clean_submitted_ids else []
        final_ids = {p.id for p in valid_permissions}

        # 2. Aplicación de la Regla Anti-Lockout para Super Administrador
        if role.name == 'super_admin':
            protected_perms = Permission.query.filter(Permission.view.in_(PROTECTED_SUPER_ADMIN_VIEWS)).all()
            protected_ids = {p.id for p in protected_perms}
            # Inyectar forzosamente los permisos protegidos si el cliente los omitió
            final_ids.update(protected_ids)

        # 3. Obtener permisos actuales para cálculo de deltas
        current_permission_roles = PermissionRole.query.filter_by(role_id=role.id).all()
        current_ids = {pr.permission_id for pr in current_permission_roles}

        added_ids = final_ids - current_ids
        removed_ids = current_ids - final_ids

        # 4. Sincronización en bloque atómico
        if removed_ids:
            PermissionRole.query.filter(
                PermissionRole.role_id == role.id,
                PermissionRole.permission_id.in_(removed_ids)
            ).delete(synchronize_session=False)

        for pid in added_ids:
            db.session.add(PermissionRole(role_id=role.id, permission_id=pid))

        db.session.flush()

        # 5. Registro de Auditoría Forense con Deltas
        BinnacleService.create_log_entry(
            module=AuditModule.CONFIGURATIONS.value,
            action_type=AuditAction.ACTUALIZAR.value,
            description=f"Actualización de matriz de permisos para el rol {role.name}",
            status=AuditStatus.COMPLETADO.value,
            target_table="sages.permissions_roles",
            record_id=role.id,
            old_values={
                "permissions_count": len(current_ids),
                "removed_ids": sorted(list(removed_ids))
            },
            new_values={
                "permissions_count": len(final_ids),
                "added_ids": sorted(list(added_ids))
            }
        )

        db.session.commit()
        logger.info(
            f"[RBAC] Permisos actualizados para rol {role.name} (ID: {role.id}) "
            f"por usuario {current_user_id}. Añadidos: {len(added_ids)}, Removidos: {len(removed_ids)}"
        )

        return {
            "role_id": role.id,
            "role_name": role.name,
            "permissions_count": len(final_ids),
            "added_ids": sorted(list(added_ids)),
            "removed_ids": sorted(list(removed_ids))
        }

    except Exception as e:
        db.session.rollback()
        logger.error(f"[RBAC] Error al actualizar permisos del rol {role_id}: {str(e)}")
        raise


