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

# ─────────────────────────────────────────────────────────────
# BLOQUE MAPA GEOGRÁFICO NACIONAL (Exclusivo super_admin)
# ─────────────────────────────────────────────────────────────

from app.dashboard.services import (
    get_map_states_distribution,
    get_state_demand_details
)


@dashboard_bp.route('/api/map/states', methods=['GET'])
@login_required
@role_required('super_admin')
@check_permissions('view_admin_panel')
def api_map_states():
    """
    Endpoint JSON con la distribución nacional coroplética de los 26 estados.
    """
    try:
        data = get_map_states_distribution()
        return jsonify({
            'success': True,
            'states': data['states'],
            'summary': data['summary']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/api/map/state-details/<int:state_id>', methods=['GET'])
@login_required
@role_required('super_admin')
@check_permissions('view_admin_panel')
def api_map_state_details(state_id):
    """
    Endpoint JSON con el detalle de demanda, top formaciones y solicitudes
    recientes para el estado seleccionado en el mapa nacional.
    """
    try:
        details = get_state_demand_details(state_id)
        if not details:
            return jsonify({
                'success': False,
                'error': f"Estado con ID {state_id} no encontrado"
            }), 404
            
        return jsonify({
            'success': True,
            'data': details
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/mapa', methods=['GET'])
@login_required
@role_required('super_admin')
@check_permissions('view_admin_panel')
def map_fullscreen_view():
    """
    Vista ampliada del Mapa Geográfico Nacional (layout 70% mapa / 30% panel).
    """
    return render_template('dashboard/map_view.html')
