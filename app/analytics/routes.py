import json
from datetime import datetime, timedelta
from flask import render_template, abort, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.analytics import analytics_bp
from app.analytics.services import AnalyticsService
from app.decorators import role_required, check_permissions
from app.models import Request, Training

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

@analytics_bp.route('/api/v1/stats', methods=['GET'])
@login_required
def get_executive_stats():
    """
    Provee los datos en formato JSON para el script analytics_dashboard.js.
    Calcula KPIs de 28 días, distribución de estatus y temas UREE.
    """
    now = datetime.utcnow()
    start_date_28d = now - timedelta(days=28)

    # 1. KPIs de los últimos 28 días
    total_requests_28d = Request.query.filter(Request.created_at >= start_date_28d).count()
    
    completed_28d = Request.query.filter(
        Request.created_at >= start_date_28d, 
        Request.status == 'EJECUTADA'
    ).count()
    
    pending_28d = Request.query.filter(
        Request.created_at >= start_date_28d, 
        Request.status.in_(['PENDIENTE', 'EN_PROCESO'])
    ).count()

    # 2. Distribución de Estatus
    status_counts = db.session.query(
        Request.status, func.count(Request.id)
    ).group_by(Request.status).all()
    donut_data = {str(status): count for status, count in status_counts}

    # 3. Evolución temporal por estatus (últimos 28 días)
    timeline_data = db.session.query(
        func.date(Request.created_at).label('date'),
        Request.status,
        func.count(Request.id)
    ).filter(Request.created_at >= start_date_28d)\
     .group_by(func.date(Request.created_at), Request.status)\
     .order_by(func.date(Request.created_at)).all()

    # 4. Temas formativos UREE más solicitados
    uree_bars = db.session.query(
        Training.name,
        func.count(Request.id).label('total')
    ).join(Request, Request.training_id == Training.id)\
     .group_by(Training.name)\
     .order_by(func.desc('total'))\
     .limit(5).all()

    return jsonify({
        "kpis": {
            "total_28d": total_requests_28d,
            "completed_28d": completed_28d,
            "pending_28d": pending_28d
        },
        "donut": donut_data,
        "timeline": [{"date": str(row.date), "status": row.status, "count": row.count} for row in timeline_data],
        "bars": [{"training": row.name, "total": row.total} for row in uree_bars]
    }), 200