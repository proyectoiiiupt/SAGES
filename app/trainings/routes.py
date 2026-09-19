"""
Rutas del Módulo de Formación (Trainings)
Bloque 1: Hub de Navegación por Módulos – Vista Principal / Landing.

Endpoints:
  GET  /training/              → index()            – Renderiza el Hub
  GET  /training/api/counts    → get_module_counts() – Conteos asíncronos por módulo y rol
"""

from flask import render_template, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from app.trainings import trainings_bp
from app.models.training_module_model import TrainingModule
from app.models.training_model import Training
from app.models.status_model import Status
from app.decorators import check_permissions
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
