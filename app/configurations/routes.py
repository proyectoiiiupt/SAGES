"""
Rutas del Módulo de Configuraciones Globales (SAGES)
Tarea: US-56-places-management
Controladores REST para: vista principal (con sedes), registro, edición,
alternancia de estatus y APIs geográficas en cascada.
"""

from flask import render_template, request, jsonify, abort
from flask_login import login_required, current_user
from app.configurations import configurations_bp
from app.decorators import role_required
from app.configurations.forms import PlaceForm
from app.configurations.services import (
    get_places_with_staff_count,
    create_place,
    update_place,
    toggle_place_status,
    get_municipalities_by_state,
    get_parishes_by_municipality
)
from app.models.state_model import State


# ─────────────────────────────────────────────────────────────────────────────
# VISTA PRINCIPAL — Panel de Configuraciones
# ─────────────────────────────────────────────────────────────────────────────

@configurations_bp.route('/', methods=['GET'])
@login_required
@role_required('super_admin')
def index():
    """
    Ruta base del módulo de configuraciones.
    Renderiza la interfaz con todas las subvistas, incluyendo el listado de
    sedes paginado con conteo de personal adscrito y el formulario de alta.
    """
    page       = request.args.get('page', 1, type=int)
    per_page   = 10
    pagination = get_places_with_staff_count(page=page, per_page=per_page)
    states     = State.query.order_by(State.name).all()
    form       = PlaceForm()

    return render_template(
        'configurations/index.html',
        pagination=pagination,
        places=pagination.items if pagination else [],
        states=states,
        form=form,
        per_page=per_page
    )


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
