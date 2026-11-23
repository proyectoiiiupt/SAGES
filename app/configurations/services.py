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
from app.models.role_user_model import RoleUser
from app.models.user_model import User
from app.models.permission_model import Permission
from app.models.permission_role_model import PermissionRole
from app.models.binnacle_model import Binnacle
from sqlalchemy.orm import joinedload
from app.binnacle.services import BinnacleService
from app.binnacle.types import AuditModule, AuditAction, AuditStatus

from datetime import datetime, timezone
import os
import uuid
import time
import shutil
from flask import current_app

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
        new_place._skip_auto_audit = True
        db.session.add(new_place)
        db.session.commit()

        try:
            BinnacleService.create_log_entry(
                module       = AuditModule.CONFIGURATIONS.value,
                action_type  = AuditAction.REGISTRO_NUEVA_SEDE.value,
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
        except Exception as audit_err:
            logger.warning(f"[configurations.create_place] Error en bitácora: {audit_err}")
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
        place._skip_auto_audit = True

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

        db.session.commit()

        try:
            BinnacleService.create_log_entry(
                module       = AuditModule.CONFIGURATIONS.value,
                action_type  = AuditAction.ACTUALIZAR_SEDE.value,
                description  = f'Sede actualizada: {place.name} ({place.place_code})',
                status       = AuditStatus.MODIFICADO.value,
                target_table = 'sages.places',
                record_id    = place.id,
                old_values   = old_values,
                new_values   = new_values
            )
        except Exception as audit_err:
            logger.warning(f"[configurations.update_place] Error en bitácora: {audit_err}")
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

        place._skip_auto_audit = True
        db.session.commit()

        try:
            BinnacleService.create_log_entry(
                module       = AuditModule.CONFIGURATIONS.value,
                action_type  = AuditAction.CAMBIO_ESTATUS_SEDE.value,
                description  = action_desc,
                status       = AuditStatus.MODIFICADO.value,
                target_table = 'sages.places',
                record_id    = place.id,
                old_values   = {'status': old_status},
                new_values   = {'status': new_status}
            )
        except Exception as audit_err:
            logger.warning(f"[configurations.toggle_place_status] Error en bitácora: {audit_err}")
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

def get_places_with_staff_count(page: int = 1, per_page: int = 10, search: str = '', state_id: int = None):
    """
    Obtiene las sedes de CORPOELEC paginadas con sus relaciones geográficas
    y el conteo de personal administrativo activo adscrito.

    Soporta búsqueda opcional por nombre o código (search) y filtro por
    estado territorial (state_id). Solo enriquece con staff_count los
    registros de la página actual para evitar N+1 queries sobre toda la tabla.

    Args:
        page     (int): Página actual (1-indexada). Default: 1.
        per_page (int): Registros por página. Default: 10.
        search   (str): Término de búsqueda por nombre o código de sede.
        state_id (int): ID del estado para filtrar geográficamente.

    Returns:
        Pagination: Objeto de paginación de Flask-SQLAlchemy con atributo
                    virtual `staff_count` en cada item de la página.
    """
    corpoelec = Company.query.filter_by(company_code='COMP-001').first()
    if not corpoelec:
        return None

    status_act = _get_active_status()

    query = (
        Place.query
        .options(
            joinedload(Place.parish)
                .joinedload(Parish.municipality)
                .joinedload(Municipality.state),
            joinedload(Place.status)
        )
        .filter(Place.company_id == corpoelec.id)
    )

    search_clean = (search or '').strip()
    if search_clean:
        pattern = f"%{search_clean}%"
        query = query.filter(
            db.or_(
                Place.name.ilike(pattern),
                Place.place_code.ilike(pattern)
            )
        )

    if state_id is not None and state_id > 0:
        query = (
            query
            .join(Place.parish)
            .join(Parish.municipality)
            .filter(Municipality.state_id == state_id)
        )

    pagination = (
        query
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

ROLE_ALLOWED_VIEWS = {
    'super_admin': {
        'view_home',
        'view_admin_panel',
        'manage_requests',
        'view_training_catalog',
        'assign_to_states',
        'upload_training',
        'view_statistics',
        'manage_users',
        'register_users',
        'manage_institution',
        'system_configuration',
    },
    'state_admin': {
        'view_home',
        'manage_requests',
        'view_training_catalog',
        'assign_to_states',
        'view_statistics',
        'manage_users',
        'register_users',
        'manage_institution',
    },
    'applicant': {
        'view_home',
        'create_request',
        'view_training_catalog',
        'view_my_institution',
    },
}


def get_permissions_grouped() -> list:
    """
    Consulta los permisos vigentes desde sages.permissions y los organiza en los
    grupos funcionales esperados por #modal-permissions, preservando los IDs DOM
    requeridos por configurations.js sin hardcodear IDs de base de datos.

    Returns:
        list[dict]: Lista de grupos con clave 'title' y 'permissions'.
    """
    perms = Permission.query.order_by(Permission.id).all()
    by_view = {p.view: p for p in perms if p.view}

    # Metadatos de presentación y contrato DOM por clave de vista (perm.view)
    view_meta = {
        'view_home': ('Ver Inicio', 'perm-item-home', 'chk-view-home', 'tag-home'),
        'view_admin_panel': ('Panel Administrativo', 'perm-item-admin-panel', 'chk-admin-panel', 'tag-admin-panel'),
        'view_statistics': ('Ver Estadísticas', 'perm-item-statistics', 'chk-statistics', None),
        'manage_requests': ('Gestionar Solicitudes', 'perm-item-manage-requests', 'chk-manage-requests', None),
        'create_request': ('Crear Solicitud', 'perm-item-create-request', 'chk-create-request', None),
        'view_training_catalog': ('Catálogo de Formación', 'perm-item-training-catalog', 'chk-training-catalog', None),
        'upload_training': ('Cargar Formación', 'perm-item-upload-training', 'chk-upload-training', None),
        'assign_to_states': ('Asignar a Estados', 'perm-item-assign-states', 'chk-assign-states', None),
        'manage_institution': ('Gestionar Institución', 'perm-item-manage-inst', 'chk-manage-inst', None),
        'view_my_institution': ('Ver Mi Institución', 'perm-item-my-inst', 'chk-my-inst', None),
        'manage_users': ('Gestionar Usuarios', 'perm-item-users', 'chk-manage-users', 'tag-manage-users'),
        'register_users': ('Registrar Usuarios', 'perm-item-register-users', 'chk-register-users', None),
        'system_configuration': ('Configuración del Sistema', 'perm-item-sys-config', 'chk-sys-config', 'tag-sys-config'),
    }

    group_specs = [
        ('Módulos Generales', ['view_home', 'view_admin_panel', 'view_statistics']),
        ('Gestión de Solicitudes UREE', ['manage_requests', 'create_request']),
        ('Gestión de Formación', ['view_training_catalog', 'upload_training']),
        ('Administración Territorial e Institucional', ['assign_to_states', 'manage_institution', 'view_my_institution']),
        ('Usuarios y Seguridad Global', ['manage_users', 'register_users', 'system_configuration']),
    ]

    used_views = set()
    groups = []

    def _serialize(perm):
        meta = view_meta.get(perm.view)
        label = meta[0] if meta else perm.name
        parent_id = meta[1] if meta else f'perm-item-{perm.id}'
        chk_id = meta[2] if meta else f'chk-perm-{perm.id}'
        tag_id = meta[3] if meta else (f'tag-perm-{perm.id}' if perm.view in PROTECTED_SUPER_ADMIN_VIEWS else None)
        return {
            'id': perm.id,
            'view': perm.view,
            'label': label,
            'parent_id': parent_id,
            'chk_id': chk_id,
            'tag_id': tag_id,
            'is_protected': perm.view in PROTECTED_SUPER_ADMIN_VIEWS,
        }

    for title, view_order in group_specs:
        items = []
        for view_key in view_order:
            perm = by_view.get(view_key)
            if perm:
                used_views.add(view_key)
                items.append(_serialize(perm))
        if items:
            groups.append({'title': title, 'permissions': items})

    # Respaldo automático si se agregan nuevos permisos en BD en el futuro
    deprecated_views = {'assign_to_educational_levels'}
    extra_items = [_serialize(p) for p in perms if p.view not in used_views and p.view not in deprecated_views]
    if extra_items:
        groups.append({'title': 'Otros Permisos del Sistema', 'permissions': extra_items})

    return groups


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
    y el conteo de usuarios activos (STAT-001) vinculados, ordenados por id.

    Returns:
        list[dict]: Estructura lista para renderizar la matriz en el frontend.
    """
    roles = Role.query.order_by(Role.id).all()
    status_act = _get_active_status()

    active_counts = {}
    if status_act:
        rows = (
            db.session.query(RoleUser.role_id, db.func.count(RoleUser.id))
            .join(User, RoleUser.user_id == User.id)
            .filter(User.status_id == status_act.id)
            .group_by(RoleUser.role_id)
            .all()
        )
        active_counts = {role_id: count for role_id, count in rows}

    matrix = []
    for r in roles:
        matrix.append({
            'id': r.id,
            'role_code': r.role_code,
            'name': r.name,
            'description': r.description,
            'permission_ids': [pr.permission_id for pr in r.permissions_assoc],
            'users_count': active_counts.get(r.id, 0) if status_act else len(r.users_assoc)
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

        # 1b. Restricción de permisos incompatibles por tipo de actor (rol)
        allowed_views = ROLE_ALLOWED_VIEWS.get(role.name)
        if allowed_views is not None:
            incompatible_views = sorted(
                p.view for p in valid_permissions if p.view and p.view not in allowed_views
            )
            if incompatible_views:
                logger.warning(
                    f"[RBAC] Intento de asignar permisos incompatibles {incompatible_views} "
                    f"al rol {role.name} por usuario {current_user_id}."
                )
                raise ValueError(
                    f"Permisos incompatibles con el rol '{role.name}': {', '.join(incompatible_views)}."
                )

        # 2. Aplicación explícita de la Regla Anti-Lockout para Super Administrador
        if role.name == 'super_admin':
            protected_perms = Permission.query.filter(Permission.view.in_(PROTECTED_SUPER_ADMIN_VIEWS)).all()
            protected_ids = {p.id for p in protected_perms}
            missing_protected = protected_ids - final_ids
            if missing_protected:
                missing_names = sorted(p.view for p in protected_perms if p.id in missing_protected)
                logger.warning(
                    f"[RBAC Anti-Lockout] Intento de revocar permisos protegidos {missing_names} "
                    f"del rol super_admin por usuario {current_user_id}."
                )
                raise ValueError(
                    "Regla Anti-Lockout: No está permitido retirar permisos críticos "
                    "del rol Super Administrador."
                )

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

        db.session.commit()

        # 5. Registro de Auditoría Forense con Deltas
        try:
            BinnacleService.create_log_entry(
                module=AuditModule.CONFIGURATIONS.value,
                action_type=AuditAction.ACTUALIZAR_MATRIZ_PERMISOS.value,
                description=f"Actualización de matriz de permisos para el rol {role.name}",
                status=AuditStatus.MODIFICADO.value,
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
        except Exception as audit_err:
            logger.warning(f"[configurations.update_role_permissions] Error en bitácora: {audit_err}")
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


# ─────────────────────────────────────────────────────────────────────────────
# GESTIÓN DE DATOS CORPORATIVOS E IDENTIDAD VISUAL (US-58)
# ─────────────────────────────────────────────────────────────────────────────

SIGNATURE_PNG = b'\x89PNG\r\n\x1a\n'
SIGNATURE_ICO = b'\x00\x00\x01\x00'

MAX_LOGO_SIZE = 2 * 1024 * 1024      # 2 MB para logotipo
MAX_ICON_SIZE = 512 * 1024           # 512 KB para favicon/icono


class FileValidationError(ValueError):
    """Error de validación binaria o de tamaño en archivo multimedia corporativo."""
    pass


def get_corporate_branding_data() -> dict:
    """
    Recupera los datos vigentes de la entidad corporativa CORPOELEC (COMP-001)
    para la precarga del formulario.
    """
    company = Company.query.filter_by(company_code='COMP-001').first()

    rif_full = ''
    if company:
        if company.identification_type and company.rif:
            rif_full = f"{company.identification_type}-{company.rif}"
        elif company.rif:
            rif_full = company.rif

    return {
        'company_name': company.company_name if company else '',
        'rif': rif_full,
        'identification_type': company.identification_type if company else '',
        'rif_number': company.rif if company else '',
        'company': company
    }


def _validate_image_bytes(file_storage, allowed_signatures: list, max_size: int, label: str):
    """
    Inspecciona en memoria el flujo binario (Magic Bytes) y el peso del archivo.
    Lanza FileValidationError si no cumple con las firmas o supera el tamaño máximo.
    """
    if not file_storage or not getattr(file_storage, 'filename', None):
        return

    # 1. Medir peso exacto
    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)

    if file_size == 0:
        raise FileValidationError(f'El archivo para "{label}" está vacío.')

    if file_size > max_size:
        max_str = f"{max_size / (1024 * 1024):.1f} MB" if max_size >= 1024 * 1024 else f"{max_size // 1024} KB"
        curr_str = f"{file_size / (1024 * 1024):.2f} MB" if file_size >= 1024 * 1024 else f"{file_size / 1024:.1f} KB"
        raise FileValidationError(
            f'El archivo "{label}" supera el tamaño máximo permitido de {max_str} ({curr_str} recibidos).'
        )

    # 2. Leer cabecera binaria (primeros 8 bytes)
    header = file_storage.read(8)
    file_storage.seek(0)

    matched = any(header.startswith(sig) for sig in allowed_signatures)
    if not matched:
        raise FileValidationError(
            f'El archivo "{label}" no posee una firma binaria válida (Magic Bytes). '
            f'Solo se admiten formatos auténticos de imagen autorizados.'
        )


def update_corporate_branding(form_data: dict, files: dict, current_user_id: int) -> dict:
    """
    Procesa de manera segura el reemplazo atómico de logotipo y favicon de CORPOELEC
    (COMP-001). Los datos fiscales (company_name, rif, identification_type) son
    inmutables por regla de negocio y nunca se sobrescriben desde la petición.

    Args:
        form_data (dict): Diccionario del formulario (conservado por compatibilidad de firma).
        files (dict): Diccionario con FileStorage opcionales ('logo_file', 'icon_file').
        current_user_id (int): ID del super administrador que ejecuta el cambio.

    Returns:
        dict: Resultado de la operación con cache_buster para refresco de UI.

    Raises:
        FileValidationError: Si algún archivo multimedia no pasa la validación binaria o de tamaño.
        Exception: Si ocurre un error en la persistencia de base de datos o sistema de archivos.
    """
    logo_file = files.get('logo_file') if files else None
    icon_file = files.get('icon_file') if files else None

    # 1. Validación preventiva de archivos antes de cualquier mutación
    if logo_file and getattr(logo_file, 'filename', None):
        _validate_image_bytes(logo_file, [SIGNATURE_PNG], MAX_LOGO_SIZE, 'Logotipo del Sistema')

    if icon_file and getattr(icon_file, 'filename', None):
        _validate_image_bytes(icon_file, [SIGNATURE_PNG, SIGNATURE_ICO], MAX_ICON_SIZE, 'Favicon / Ícono Institucional')

    try:
        # 2. Consulta de la entidad corporativa maestra (datos fiscales inmutables)
        company = Company.query.filter_by(company_code='COMP-001').first()
        if not company:
            raise ValueError("No se encontró la empresa institucional CORPOELEC (COMP-001) en la base de datos.")

        old_company_name = company.company_name
        old_rif = f"{company.identification_type}-{company.rif}" if company.identification_type else company.rif

        company._skip_auto_audit = True

        # 3. Procesamiento y reemplazo atómico de archivos estáticos
        static_img_dir = os.path.join(current_app.root_path, 'static', 'img')
        backup_dir = os.path.join(static_img_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp_str = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')

        # Logotipo
        if logo_file and getattr(logo_file, 'filename', None):
            target_logo = os.path.join(static_img_dir, 'logo_corpoelec.png')
            if os.path.exists(target_logo):
                backup_logo = os.path.join(backup_dir, f"backup_logo_{timestamp_str}_{uuid.uuid4().hex[:8]}.png")
                shutil.copy2(target_logo, backup_logo)

            temp_logo = os.path.join(static_img_dir, f"tmp_logo_{uuid.uuid4().hex}.png")
            logo_file.seek(0)
            logo_file.save(temp_logo)
            os.replace(temp_logo, target_logo)
            logger.info(f"[Branding] Logotipo actualizado exitosamente por usuario {current_user_id}.")

        # Favicon / Ícono
        if icon_file and getattr(icon_file, 'filename', None):
            target_icon = os.path.join(static_img_dir, 'icon_corpoelec.png')
            if os.path.exists(target_icon):
                backup_icon = os.path.join(backup_dir, f"backup_icon_{timestamp_str}_{uuid.uuid4().hex[:8]}.png")
                shutil.copy2(target_icon, backup_icon)

            temp_icon = os.path.join(static_img_dir, f"tmp_icon_{uuid.uuid4().hex}.png")
            icon_file.seek(0)
            icon_file.save(temp_icon)
            os.replace(temp_icon, target_icon)
            logger.info(f"[Branding] Favicon/ícono institucional actualizado exitosamente por usuario {current_user_id}.")

        db.session.commit()

        # 4. Auditoría Forense en sages.binnacle
        logo_updated = bool(logo_file and getattr(logo_file, 'filename', None))
        icon_updated = bool(icon_file and getattr(icon_file, 'filename', None))

        try:
            BinnacleService.create_log_entry(
                module=AuditModule.CONFIGURATIONS.value,
                action_type=AuditAction.ACTUALIZAR_IDENTIDAD_CORPORATIVA.value,
                description="Actualización de datos corporativos e identidad visual de CORPOELEC (COMP-001)",
                status=AuditStatus.MODIFICADO.value,
                target_table='sages.companies',
                record_id=company.id,
                old_values={
                    'company_name': old_company_name,
                    'rif': old_rif
                },
                new_values={
                    'company_name': company.company_name,
                    'rif': f"{company.identification_type}-{company.rif}",
                    'logo_reemplazado': 'SÍ' if logo_updated else 'NO',
                    'favicon_reemplazado': 'SÍ' if icon_updated else 'NO'
                }
            )
        except Exception as audit_err:
            logger.warning(f"[configurations.update_corporate_branding] Error en bitácora: {audit_err}")

        cache_buster = int(time.time())
        return {
            'success': True,
            'message': 'Identidad visual actualizada exitosamente.',
            'company_name': company.company_name,
            'cache_buster': cache_buster
        }

    except FileValidationError:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Branding] Error al actualizar datos corporativos: {str(e)}")
        raise
