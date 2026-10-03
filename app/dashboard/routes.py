"""
Rutas del Módulo de Dashboard (Panel Administrativo)
Controla la visualización de los indicadores y métricas del sistema.
"""
from flask import render_template, flash
from flask_login import login_required, current_user
from app.dashboard import dashboard_bp
from app.dashboard.services import get_dashboard_indicators, get_audit_logs
from app.decorators import role_required, check_permissions
from flask import jsonify
from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from app.models import Request, Training


@dashboard_bp.route('/', methods=['GET'], strict_slashes=False)
@dashboard_bp.route('', methods=['GET'], strict_slashes=False)
@login_required
@role_required('super_admin', 'state_admin')
@check_permissions('view_admin_panel')
def index():
    """
    Vista principal del Panel Administrativo (Dashboard).
    Muestra los indicadores superiores automatizados y métricas por jurisdicción.
    """
    try:
        metrics = get_dashboard_indicators(current_user)
        recent_logs = get_audit_logs(limit=5)
        
        return render_template('dashboard/dashboard.html', metrics=metrics, logs=recent_logs)
    except Exception as e:
        print(f"Error al cargar el dashboard: {e}")
        flash("Ocurrió un error al calcular los indicadores del panel.", "danger")
        return render_template('dashboard/dashboard.html', metrics={
            'total_requests': 0,
            'active_users': 0,
            'resolution_rate': 0,
            'pending_requests': 0,
            'attended_requests': 0,
            'in_process_requests': 0,
            'planned_requests': 0,
            'jurisdiction_label': "Panel Administrativo",
            'is_super_admin': False,
            'user_state': None,
            'jurisdiction_summary': []
        }, logs=[])


@dashboard_bp.route('/registro-auditoria', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
@check_permissions('view_admin_panel')
def audit_view():
    """
    Vista ampliada de la tabla de bitácora/auditoría (US-25-binnacle-table).
    """
    logs = get_audit_logs()
    return render_template('dashboard/audit_log.html', logs=logs)

@dashboard_bp.route('/estadisticas-ejecutivas', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
@check_permissions('view_admin_panel')
def executive_dashboard():
    """
    Vista principal del Tablero Ejecutivo de Estadísticas (US-53).
    Renderiza el archivo index.html que contiene los contenedores de los gráficos.
    """
    return render_template('dashboard/index.html')


@dashboard_bp.route('/api/v1/stats', methods=['GET'])
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
        Request.status == 'EJECUTADA' # Ajusta si usas un Enum en tus modelos
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