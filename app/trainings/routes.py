"""
Rutas del Módulo de Formación (Trainings)
Bloque 1: Hub de Navegación por Módulos – Vista Principal / Landing.

Endpoints:
  GET  /training/              → index()            – Renderiza el Hub
  GET  /training/api/counts    → get_module_counts() – Conteos asíncronos por módulo y rol
"""

import re
from datetime import datetime, time
from flask import render_template, jsonify, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func

from app.trainings import trainings_bp
from app.trainings.forms import TrainingModuleForm
from app.models.training_module_model import TrainingModule
from app.models.training_model import Training
from app.models.status_model import Status
from app.decorators import check_permissions, role_required
from app.utils.binnacle_utils import log_action
from app.extensions import db


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _get_user_role() -> str:
    """Devuelve el nombre del primer rol del usuario en sesión o 'applicant'."""
    if current_user.is_authenticated and getattr(current_user, 'roles_assoc', None):
        return current_user.roles_assoc[0].role.name
    return 'applicant'


def _is_super_admin() -> bool:
    return _get_user_role() == 'super_admin'


def _is_admin() -> bool:
    """True para super_admin y state_admin."""
    return _get_user_role() in ('super_admin', 'state_admin')


# ---------------------------------------------------------------------------
# Ruta principal: Hub de Navegación
# ---------------------------------------------------------------------------

@trainings_bp.route('/', methods=['GET'])
@login_required
@check_permissions('view_training_catalog')
def index():
    """
    Vista de entrada al catálogo de Formación.
    Renderiza los 4 Módulos Rectores de la UREE en una cuadrícula responsiva.
    """
    modules = (
        TrainingModule.query
        .filter_by(is_active=True)
        .order_by(TrainingModule.order_index)
        .all()
    )

    return render_template(
        'trainings/hub.html',
        modules=modules,
        is_super_admin=_is_super_admin(),
        is_admin=_is_admin(),
        user_role=_get_user_role(),
    )


# ---------------------------------------------------------------------------
# Endpoint API: Conteos asíncronos de temas por módulo
# ---------------------------------------------------------------------------

@trainings_bp.route('/api/counts', methods=['GET'])
@login_required
def get_module_counts():
    """
    Devuelve el conteo de temas formativos por módulo rector, adaptado al rol.

    Lógica de filtrado:
      – Base obligatoria: Training.deleted_at IS NULL (borrado lógico).
      – Rol applicant    → Solo temas con status_code == 'STAT-001' (Activos).
      – Roles admin      → Temas activos (STAT-001) + total no eliminado.

    Respuesta JSON:
    {
      "success": true,
      "is_admin": <bool>,
      "counts": {
        "<module_id>": { "active": <int>, "total": <int> }
      }
    }
    """
    role = _get_user_role()
    is_admin = role in ('super_admin', 'state_admin')

    try:
        # Sub-consulta base: temas no eliminados
        base_q = (
            db.session.query(
                Training.training_module_id,
                func.count(Training.id).label('total')
            )
            .filter(Training.deleted_at.is_(None))
            .group_by(Training.training_module_id)
        )

        # Sub-consulta de temas activos (STAT-001) sin eliminar
        active_q = (
            db.session.query(
                Training.training_module_id,
                func.count(Training.id).label('active')
            )
            .join(Status, Training.status_id == Status.id)
            .filter(
                Training.deleted_at.is_(None),
                Status.status_code == 'STAT-001'
            )
            .group_by(Training.training_module_id)
        )

        total_rows = {row.training_module_id: row.total for row in base_q.all()}
        active_rows = {row.training_module_id: row.active for row in active_q.all()}

        # Obtener todos los módulos activos para incluirlos (aunque tengan 0 temas)
        module_ids = [
            m.id for m in TrainingModule.query.filter_by(is_active=True).all()
        ]

        counts = {}
        for mid in module_ids:
            active_count = active_rows.get(mid, 0)
            total_count = total_rows.get(mid, 0)

            if is_admin:
                counts[str(mid)] = {
                    'active': active_count,
                    'total': total_count
                }
            else:
                # Para solicitantes solo se exponen los temas activos
                counts[str(mid)] = {
                    'active': active_count,
                    'total': active_count
                }

        return jsonify({
            'success': True,
            'is_admin': is_admin,
            'counts': counts
        }), 200

    except Exception as e:
        import logging
        logging.error(f"[trainings.get_module_counts] Error al calcular conteos: {e}")
        return jsonify({
            'success': False,
            'message': 'No se pudieron cargar los contadores en este momento.',
            'counts': {}
        }), 500


# ---------------------------------------------------------------------------
# Vista Tabular Maestra: Listado Administrativo de Formaciones
# Bloque 3: Gestión Administrativa Centralizada
# ---------------------------------------------------------------------------

@trainings_bp.route('/list', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
def list_all():
    """
    Vista alternativa tabular accesible para Super Administrador y Administradores Estadales.
    Permite buscar por término, filtrar por Módulo, Estatus (Activo/Inactivo) y Fecha de creación,
    con paginación de 10 en 10 registros.

    Nota de alcance:
      - La ejecución de acciones de edición y borrado lógico está reservada para una tarea posterior.
      - La consulta filtra temas no eliminados mediante la cláusula Training.deleted_at.is_(None).
    """
    # 1. Validación de tipos numéricos para paginación
    page = request.args.get('page', 1, type=int)
    if not page or page < 1:
        page = 1

    per_page = request.args.get('per_page', 10, type=int)
    if not per_page or per_page < 1 or per_page > 50:
        per_page = 10

    # 2. Parámetros de búsqueda y filtros
    search_query = request.args.get('search', '').strip()
    filter_module = request.args.get('module_id', '').strip()
    filter_status = request.args.get('status', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    filters = {
        'search': search_query,
        'module_id': filter_module,
        'status': filter_status,
        'date_from': date_from,
        'date_to': date_to,
        'per_page': per_page
    }

    try:
        # Consulta base: temas no eliminados (borrado lógico: Training.deleted_at IS NULL)
        # Nota: La ejecución de borrado lógico y edición se implementará en una tarea posterior.
        query = (
            Training.query
            .join(TrainingModule, Training.training_module_id == TrainingModule.id)
            .join(Status, Training.status_id == Status.id)
            .filter(Training.deleted_at.is_(None))
        )

        # Búsqueda por nombre del tema formativo
        if search_query:
            sanitized_term = search_query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            search_pattern = f"%{sanitized_term}%"
            query = query.filter(Training.name.ilike(search_pattern))

        # Filtro por Módulo Rector
        if filter_module and filter_module.isdigit():
            query = query.filter(Training.training_module_id == int(filter_module))

        # Filtro por Estatus (Activo/Inactivo: STAT-001 / STAT-002 o status_id)
        if filter_status:
            if filter_status.isdigit():
                query = query.filter(Training.status_id == int(filter_status))
            else:
                query = query.filter(Status.status_code == filter_status)

        # Filtro por Rango de Fecha de Creación
        if date_from:
            try:
                dt_from = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(Training.created_at >= dt_from)
            except ValueError:
                pass

        if date_to:
            try:
                dt_to = datetime.strptime(date_to, '%Y-%m-%d')
                dt_to = datetime.combine(dt_to.date(), time.max)
                query = query.filter(Training.created_at <= dt_to)
            except ValueError:
                pass

        # Ordenamiento natural secuencial por número de formación
        query = query.order_by(Training.id.asc())

        # Paginación optimizada usando SQLAlchemy con offset y limit (mediante paginate)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        trainings = pagination.items

        # Catálogos de opciones para filtros
        modules = (
            TrainingModule.query
            .filter_by(is_active=True)
            .order_by(TrainingModule.order_index)
            .all()
        )
        statuses = (
            Status.query
            .filter(Status.status_code.in_(['STAT-001', 'STAT-002']))
            .order_by(Status.id)
            .all()
        )

        return render_template(
            'trainings/list.html',
            trainings=trainings,
            pagination=pagination,
            modules=modules,
            statuses=statuses,
            filters=filters,
            is_super_admin=_is_super_admin(),
            is_admin=_is_admin(),
            user_role=_get_user_role()
        )

    except Exception as e:
        import logging
        logging.error(f"[trainings.list_all] Error al obtener listado de formaciones: {e}")
        return render_template(
            'trainings/list.html',
            trainings=[],
            pagination=None,
            modules=TrainingModule.query.filter_by(is_active=True).order_by(TrainingModule.order_index).all(),
            statuses=Status.query.filter(Status.status_code.in_(['STAT-001', 'STAT-002'])).all(),
            filters=filters,
            is_super_admin=_is_super_admin(),
            is_admin=_is_admin(),
            user_role=_get_user_role(),
            error_message="No se pudo cargar el listado de formaciones en este momento."
        )


# ---------------------------------------------------------------------------
# Registro de Nuevo Módulo Rector
# ---------------------------------------------------------------------------

def _generate_next_module_code() -> str:
    """
    Genera el siguiente código correlativo MOD-XXX en backend.
    Extrae la secuencia numérica de códigos existentes con prefijo 'MOD-' y genera el próximo (ej. MOD-005).
    """
    all_codes = db.session.query(TrainingModule.module_code).all()
    max_num = 0
    for (code,) in all_codes:
        if code and code.startswith('MOD-'):
            suffix = code[4:]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
    next_num = max_num + 1
    return f"MOD-{next_num:03d}"


def _get_next_order_index() -> int:
    """Calcula el siguiente índice de orden disponible."""
    max_order = db.session.query(func.max(TrainingModule.order_index)).scalar()
    return (max_order or 0) + 1


@trainings_bp.route('/module/new', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def new_module():
    """
    Ruta para registrar un nuevo Módulo Rector.
    - Captura: nombre, descripción y orden de visualización.
    - El código MOD-XXX es generado internamente por la base de datos/backend.
    - Solo accesible para usuarios con rol 'super_admin'.
    """
    form = TrainingModuleForm()

    # Pre-calcular sugerencia de código para el formulario
    suggested_code = _generate_next_module_code()

    if request.method == 'GET':
        form.module_code.data = suggested_code

    if form.validate_on_submit():
        try:
            # Siempre se autogenera el código en backend para evitar manipulación manual
            final_code = _generate_next_module_code()

            new_mod = TrainingModule(
                module_code=final_code,
                name=form.name.data.strip(),
                description=form.description.data.strip(),
                order_index=_get_next_order_index(),
                is_active=True
            )
            db.session.add(new_mod)
            db.session.commit()

            # Registro en bitácora del sistema
            try:
                log_action(
                    user_id=current_user.id,
                    module='trainings',
                    action_type='CREATE',
                    description=f"Registro de nuevo Módulo Rector: {new_mod.name} ({new_mod.module_code})",
                    new_values={
                        'module_code': new_mod.module_code,
                        'name': new_mod.name,
                        'description': new_mod.description,
                        'order_index': new_mod.order_index
                    }
                )
            except Exception as log_err:
                import logging
                logging.warning(f"[trainings.new_module] No se pudo registrar en bitácora: {log_err}")

            flash(f'Módulo Rector "{new_mod.name}" registrado exitosamente.', "success")
            return redirect(url_for('trainings.index'))

        except Exception as e:
            db.session.rollback()
            import logging
            logging.error(f"[trainings.new_module] Error al registrar módulo: {e}")
            flash("Ocurrió un error inesperado al registrar el Módulo Rector. Intente nuevamente.", "danger")
    elif request.method == 'POST':
        flash("Por favor, verifica los campos obligatorios del formulario.", "warning")

    return render_template(
        'trainings/module_new.html',
        form=form,
        suggested_code=suggested_code,
        is_super_admin=_is_super_admin(),
        is_admin=_is_admin(),
        user_role=_get_user_role()
    )

