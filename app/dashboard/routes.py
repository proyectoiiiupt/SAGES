"""
Rutas del Módulo de Dashboard (Panel Administrativo)
Controla la visualización de los indicadores y métricas del sistema.
"""
from flask import render_template, flash
from flask_login import login_required, current_user
from app.dashboard import dashboard_bp
from app.dashboard.services import get_dashboard_indicators
from app.decorators import role_required, check_permissions


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
        return render_template('dashboard/dashboard.html', metrics=metrics)
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
        })
