"""
Rutas del Módulo de Configuraciones Globales (SAGES)
Tareas:
  - US-56-places-management: Controladores REST para sedes operativas y APIs geográficas.
  - US-58-corporate-branding: Controlador para actualización de datos corporativos e identidad visual.
"""

from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.configurations import configurations_bp
from app.decorators import role_required
from app.extensions import limiter
from app.configurations.forms import PlaceForm, CorporateDataForm
from app.configurations.services import (
    get_places_with_staff_count,
    create_place,
    update_place,
    toggle_place_status,
    get_municipalities_by_state,
    get_parishes_by_municipality,
    get_role_permissions,
    get_all_roles_matrix,
    update_role_permissions,
    get_last_backup_log,
    get_corporate_branding_data,
    update_corporate_branding,
    FileValidationError
)
from app.models.state_model import State
from app.models.place_model import Place
from app.notifications.services import NotificationService
from app.notifications.enums import NotificationEvent, NotificationType

# ---------------------------------------------------------------------------
# Helpers Privados
# ---------------------------------------------------------------------------

def _get_actor_name(user) -> str:
    """Extrae el nombre completo formateado del usuario en sesión."""
    if user and hasattr(user, 'person') and user.person:
        p = user.person
        return f"{p.first_name or ''} {p.last_name or ''}".strip() or getattr(user, 'user_name', 'Administrador')
    return getattr(user, 'user_name', 'Administrador')


# ─────────────────────────────────────────────────────────────────────────────
# VISTA PRINCIPAL — Panel de Configuraciones
# ─────────────────────────────────────────────────────────────────────────────

@configurations_bp.route('/', methods=['GET'])
@login_required
@role_required('super_admin')
def index():
    """
    Ruta base del módulo de configuraciones.
    Renderiza la interfaz con todas las subvistas, incluyendo datos corporativos,
    matriz de roles, listado de sedes paginado y monitoreo de respaldos.
    """
    page       = request.args.get('page', 1, type=int)
    per_page   = 10
    pagination = get_places_with_staff_count(page=page, per_page=per_page)
    states     = State.query.order_by(State.name).all()
    form       = PlaceForm()
    roles_matrix = get_all_roles_matrix()
    last_backup = get_last_backup_log()

    # Precarga de datos corporativos e identidad visual (US-58)
    corporate_data = get_corporate_branding_data()
    corporate_form = CorporateDataForm(data={
        'company_name': corporate_data.get('company_name', ''),
        'rif': corporate_data.get('rif', ''),
        'central_phone': corporate_data.get('central_phone', ''),
        'fiscal_address': corporate_data.get('fiscal_address', '')
    })

    return render_template(
        'configurations/index.html',
        pagination=pagination,
        places=pagination.items if pagination else [],
        states=states,
        form=form,
        corporate_form=corporate_form,
        corporate_data=corporate_data,
        per_page=per_page,
        roles_matrix=roles_matrix,
        last_backup=last_backup
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT DE DATOS CORPORATIVOS E IDENTIDAD VISUAL (US-58)
# ─────────────────────────────────────────────────────────────────────────────

@configurations_bp.route('/corporate', methods=['POST'])
@login_required
@role_required('super_admin')
@limiter.limit("10 per minute", methods=['POST'], key_func=lambda: str(current_user.id))
def update_corporate():
    """
    Actualiza la información oficial de CORPOELEC (razón social, RIF, teléfono central,
    dirección fiscal) y procesa la sustitución atómica y segura de logotipo y favicon.

    Returns:
        JSON 200: Éxito con mensaje y cache_buster para refrescar imágenes en UI.
        JSON 400: Error de validación binaria (Magic Bytes) o peso de archivo.
        JSON 422: Validación fallida en campos de texto de CorporateDataForm.
        JSON 500: Error interno no controlado.
    """
    form = CorporateDataForm(request.form)

    if not form.validate_on_submit():
        return jsonify({
            'success': False,
            'message': 'Existen inconsistencias en los campos del formulario.',
            'errors': form.errors
        }), 422

    try:
        files = {
            'logo_file': request.files.get('logo_file'),
            'icon_file': request.files.get('icon_file')
        }
        result = update_corporate_branding(form.data, files, current_user.id)

        # Notificación Post-Commit: Actualización de datos corporativos
        try:
            admin_name = _get_actor_name(current_user)
            company_name = form.data.get('company_name', 'CORPOELEC')
            rif_val = form.data.get('rif', '')
            phone_val = form.data.get('central_phone', '')
            ctx = {
                "admin_name": admin_name,
                "company_name": company_name,
                "updated_fields": f"RIF: {rif_val}, Teléfono: {phone_val}"
            }
            NotificationService.notify_role(
                role_name="state_admin",
                event=NotificationEvent.CONFIG_CORPORATE_UPDATED,
                context=ctx
            )
            NotificationService.notify_role(
                role_name="super_admin",
                event=NotificationEvent.CONFIG_CORPORATE_UPDATED,
                context=ctx,
                exclude_user_id=current_user.id,
                redirect_url="/configurations/",
                action_text="Ver Configuración"
            )
        except Exception as notif_err:
            import logging
            logging.getLogger(__name__).warning(f"No se pudo emitir notificación CONFIG_CORPORATE_UPDATED: {notif_err}")

        return jsonify(result), 200

    except FileValidationError as fve:
        return jsonify({
            'success': False,
            'message': str(fve)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error interno al procesar los datos corporativos: {str(e)}'
        }), 500


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT DE REGISTRO DE SEDE
# ─────────────────────────────────────────────────────────────────────────────

@configurations_bp.route('/places/new', methods=['POST'])
@login_required
@role_required('super_admin')
def new_place():
    """
    Registra una nueva sede operativa.
    Acepta FormData con CSRF token. Valida con PlaceForm y delega al servicio.

    Returns:
        JSON 201: {"success": True, "message": "...", "place_code": "PLC-XXX"}
        JSON 422: {"success": False, "errors": {...}} — validación fallida
        JSON 500: {"success": False, "message": "..."} — error de BD
    """
    form = PlaceForm()

    # Inyectar choices dinámicos para que WTForms pueda validar los SelectField
    # de municipio y parroquia que vienen del cliente vía AJAX
    _inject_dynamic_choices(form)

    if not form.validate_on_submit():
        return jsonify({'success': False, 'errors': form.errors}), 422

    try:
        new = create_place(form.data, current_user.id)

        # Notificación Post-Commit: Nueva sede operativa registrada
        try:
            admin_name = _get_actor_name(current_user)
            state_id = new.parish.municipality.state_id if (new.parish and new.parish.municipality) else None
            state_name = new.parish.municipality.state.name if (new.parish and new.parish.municipality and new.parish.municipality.state) else "Jurisdicción Estadal"
            ctx = {
                "admin_name": admin_name,
                "place_name": new.name,
                "state_name": state_name
            }
            if state_id:
                NotificationService.notify_role(
                    role_name="state_admin",
                    event=NotificationEvent.CONFIG_PLACE_CREATED,
                    context=ctx,
                    state_id=state_id,
                    exclude_user_id=current_user.id
                )
            NotificationService.notify_role(
                role_name="super_admin",
                event=NotificationEvent.CONFIG_PLACE_CREATED,
                context=ctx,
                exclude_user_id=current_user.id,
                redirect_url="/configurations/",
                action_text="Ver Sedes"
            )
        except Exception as notif_err:
            import logging
            logging.getLogger(__name__).warning(f"No se pudo emitir notificación CONFIG_PLACE_CREATED: {notif_err}")

        return jsonify({
            'success'   : True,
            'message'   : f'Sede "{new.name}" registrada exitosamente con código {new.place_code}.',
            'place_code': new.place_code
        }), 201

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT DE EDICIÓN DE SEDE
# ─────────────────────────────────────────────────────────────────────────────

@configurations_bp.route('/places/<int:place_id>/edit', methods=['POST'])
@login_required
@role_required('super_admin')
def edit_place(place_id):
    """
    Actualiza los datos de una sede existente.
    Acepta FormData. No modifica place_code ni company_id.

    Returns:
        JSON 200: {"success": True, "message": "..."}
        JSON 422: {"success": False, "errors": {...}}
        JSON 500: {"success": False, "message": "..."}
    """
    form = PlaceForm()
    _inject_dynamic_choices(form)

    if not form.validate_on_submit():
        return jsonify({'success': False, 'errors': form.errors}), 422

    try:
        updated = update_place(place_id, form.data, current_user.id)

        # Notificación Post-Commit: Datos de sede actualizados (al personal adscrito a esa sede)
        try:
            admin_name = _get_actor_name(current_user)
            NotificationService.notify_place_staff(
                place_id=place_id,
                event=NotificationEvent.CONFIG_PLACE_UPDATED,
                context={
                    "place_name": updated.name,
                    "admin_name": admin_name
                },
                exclude_user_id=current_user.id
            )
        except Exception as notif_err:
            import logging
            logging.getLogger(__name__).warning(f"No se pudo emitir notificación CONFIG_PLACE_UPDATED: {notif_err}")

        return jsonify({
            'success': True,
            'message': f'Sede "{updated.name}" actualizada correctamente.'
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT DE ALTERNANCIA DE ESTATUS (con integridad referencial)
# ─────────────────────────────────────────────────────────────────────────────

@configurations_bp.route('/places/<int:place_id>/toggle-status', methods=['POST'])
@login_required
@role_required('super_admin')
def toggle_status(place_id):
    """
    Alterna el estatus operativo de una sede entre Activo e Inactivo.

    Regla de integridad referencial: si la sede tiene personal activo
    adscrito en company_staff, la operación de inactivación es BLOQUEADA
    y se retorna HTTP 409 Conflict con mensaje explicativo.

    Returns:
        JSON 200: {"success": True, "message": "..."}
        JSON 409: {"success": False, "message": "...", "staff_count": N}
        JSON 500: {"success": False, "message": "..."}
    """
    try:
        success, message, staff_count = toggle_place_status(place_id, current_user.id)

        if not success:
            return jsonify({
                'success'    : False,
                'message'    : message,
                'staff_count': staff_count
            }), 409

        # Notificación Post-Commit: Cambio de estatus operativo de sede
        try:
            place = Place.query.get(place_id)
            if place:
                admin_name = _get_actor_name(current_user)
                is_active = (place.status.status_code == 'STAT-001') if place.status else False
                sev = NotificationType.SUCCESS if is_active else NotificationType.WARNING
                action_lbl = "reactivada para operaciones" if is_active else "inactivada temporalmente"
                state_id = place.parish.municipality.state_id if (place.parish and place.parish.municipality) else None
                state_name = place.parish.municipality.state.name if (place.parish and place.parish.municipality and place.parish.municipality.state) else "Jurisdicción Estadal"

                ctx = {
                    "place_name": place.name,
                    "state_name": state_name,
                    "action_label": action_lbl,
                    "admin_name": admin_name
                }
                if state_id:
                    NotificationService.notify_role(
                        role_name="state_admin",
                        event=NotificationEvent.CONFIG_PLACE_STATUS_CHANGED,
                        context=ctx,
                        state_id=state_id,
                        exclude_user_id=current_user.id,
                        severity_override=sev
                    )
                NotificationService.notify_role(
                    role_name="super_admin",
                    event=NotificationEvent.CONFIG_PLACE_STATUS_CHANGED,
                    context=ctx,
                    exclude_user_id=current_user.id,
                    severity_override=sev,
                    redirect_url="/configurations/",
                    action_text="Ver Sedes"
                )
        except Exception as notif_err:
            import logging
            logging.getLogger(__name__).warning(f"No se pudo emitir notificación CONFIG_PLACE_STATUS_CHANGED: {notif_err}")

        return jsonify({'success': True, 'message': message}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# APIs GEOGRÁFICAS EN CASCADA (sin restricción de rol para carga dinámica)
# ─────────────────────────────────────────────────────────────────────────────

@configurations_bp.route('/api/municipalities/<int:state_id>', methods=['GET'])
@login_required
def api_municipalities(state_id):
    """
    Retorna la lista de municipios de un estado dado en formato JSON.
    Consumida por la cascada geográfica del modal de sedes vía fetch().

    Returns:
        JSON: [{"id": int, "name": str}, ...]
    """
    data = get_municipalities_by_state(state_id)
    return jsonify(data), 200


@configurations_bp.route('/api/parishes/<int:municipality_id>', methods=['GET'])
@login_required
def api_parishes(municipality_id):
    """
    Retorna la lista de parroquias de un municipio dado en formato JSON.
    Consumida por la cascada geográfica del modal de sedes vía fetch().

    Returns:
        JSON: [{"id": int, "name": str}, ...]
    """
    data = get_parishes_by_municipality(municipality_id)
    return jsonify(data), 200


# ─────────────────────────────────────────────────────────────────────────────
# HELPER INTERNO: inyectar choices dinámicos para validación WTForms
# ─────────────────────────────────────────────────────────────────────────────

def _inject_dynamic_choices(form: PlaceForm) -> None:
    """
    Inyecta los choices de municipality_id y parish_id en el formulario
    antes de la validación, usando los valores enviados en el request.
    Esto es necesario porque WTForms valida que el valor seleccionado
    esté en la lista de choices, pero estas listas son dinámicas (por AJAX).
    """
    from app.models.municipality_model import Municipality
    from app.models.parish_model import Parish

    # Obtener los valores enviados desde el cliente
    mun_id    = request.form.get('municipality_id', 0, type=int)
    parish_id = request.form.get('parish_id', 0, type=int)

    # Reconstruir los choices mínimos necesarios para que WTForms los acepte
    mun = Municipality.query.get(mun_id)
    par = Parish.query.get(parish_id)

    form.municipality_id.choices = [(mun_id, mun.name if mun else '')] if mun_id else [(0, '')]
    form.parish_id.choices       = [(parish_id, par.name if par else '')] if parish_id else [(0, '')]


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS DE GESTIÓN DE MATRIZ DE PERMISOS (RBAC) - US-54 / US-57
# ─────────────────────────────────────────────────────────────────────────────

@configurations_bp.route('/roles/<int:role_id>/permissions', methods=['GET'])
@login_required
@role_required('super_admin')
def get_role_permissions_endpoint(role_id):
    """
    Retorna los privilegios actualmente asignados a un rol para poblar el modal.

    Returns:
        JSON 200: {"success": True, "data": {"role_id": int, "role_code": str, "permission_ids": [...]}}
        JSON 404: {"success": False, "message": "..."}
    """
    try:
        data = get_role_permissions(role_id)
        return jsonify({'success': True, 'data': data}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al consultar permisos: {str(e)}'}), 404


@configurations_bp.route('/roles/<int:role_id>/permissions', methods=['POST'])
@login_required
@role_required('super_admin')
@limiter.limit("20 per minute", methods=['POST'], key_func=lambda: str(current_user.id))
def update_role_permissions_endpoint(role_id):
    """
    Sincroniza atómicamente la matriz de permisos para un rol específico.
    Protegido contra CSRF, sesión autenticada, rol super_admin y Rate Limiting.

    Payload JSON esperado:
        {"permission_ids": [1, 2, 5, ...]}

    Returns:
        JSON 200: {"success": True, "message": "Niveles de acceso actualizados exitosamente.", "deltas": {...}}
        JSON 400: {"success": False, "message": "Cuerpo de la petición inválido o ID de rol erróneo."}
        JSON 500: {"success": False, "message": "Ocurrió un error al persistir los cambios."}
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or 'permission_ids' not in payload or not isinstance(payload['permission_ids'], list):
        return jsonify({
            'success': False,
            'message': 'Cuerpo de la petición inválido. Se requiere "permission_ids" como lista.'
        }), 400

    try:
        result = update_role_permissions(role_id, payload['permission_ids'], current_user.id)

        # Notificación Post-Commit: Actualización de permisos de rol
        try:
            added_count = len(result.get("added_ids", []))
            removed_count = len(result.get("removed_ids", []))
            if added_count > 0 or removed_count > 0:
                admin_name = _get_actor_name(current_user)
                sev = NotificationType.WARNING if removed_count > 0 else NotificationType.INFO
                summary_parts = []
                if added_count:
                    summary_parts.append(f"+{added_count} habilitados")
                if removed_count:
                    summary_parts.append(f"-{removed_count} revocados")
                changes_summary = ", ".join(summary_parts)

                ctx = {
                    "admin_name": admin_name,
                    "role_name": result["role_name"],
                    "changes_summary": changes_summary
                }
                # 1. Notificar a los usuarios activos que poseen el rol modificado
                NotificationService.notify_role(
                    role_name=result["role_name"],
                    event=NotificationEvent.CONFIG_ROLE_PERMISSIONS_UPDATED,
                    context=ctx,
                    exclude_user_id=current_user.id,
                    severity_override=sev
                )
                # 2. Notificar a otros Super Administradores
                if result["role_name"].lower() != "super_admin":
                    NotificationService.notify_role(
                        role_name="super_admin",
                        event=NotificationEvent.CONFIG_ROLE_PERMISSIONS_UPDATED,
                        context=ctx,
                        exclude_user_id=current_user.id,
                        severity_override=sev,
                        redirect_url="/configurations/",
                        action_text="Ver Matriz RBAC"
                    )
        except Exception as notif_err:
            import logging
            logging.getLogger(__name__).warning(f"No se pudo emitir notificación CONFIG_ROLE_PERMISSIONS_UPDATED: {notif_err}")

        return jsonify({
            'success': True,
            'message': 'Niveles de acceso actualizados exitosamente.',
            'deltas': result
        }), 200

    except ValueError as ve:
        return jsonify({
            'success': False,
            'message': str(ve)
        }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Ocurrió un error al persistir los cambios.'
        }), 500
