import json
from flask import render_template, abort, flash
from flask_login import login_required, current_user

from app.analytics import analytics_bp
from app.analytics.services import AnalyticsService
from app.decorators import role_required, check_permissions

@analytics_bp.route('/', methods=['GET'])
@analytics_bp.route('/index', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
@check_permissions('view_statistics')
def index():
    """
    Vista 1: Tablero Ejecutivo "Reportes y Estadísticas".
    """
    try:
        metrics = AnalyticsService.get_dashboard_metrics(current_user)
        
        return render_template(
            'analytics/index.html',
            metrics=metrics,
            # Se serializa a JSON para inicialización segura en Chart.js sin llamadas adicionales
            metrics_json=json.dumps(metrics)
        )
    except Exception as e:
        print(f"[ERROR analytics.index]: {e}")
        flash("Ocurrió un error al cargar las estadísticas del sistema.", "danger")
        return render_template(
            'analytics/index.html',
            metrics={
                'kpi_28_dias': 0,
                'diferencial_pct': 0.0,
                'jurisdiction_label': "Jurisdicción Asignada",
                'donut': {'aprobadas': 0, 'en_proceso': 0, 'pendientes': 0, 'total': 0},
                'lines': {'labels': [], 'aprobadas': [], 'en_proceso': [], 'pendientes': []},
                'bars': {'labels': [], 'data': []}
            },
            metrics_json=json.dumps({})
        )