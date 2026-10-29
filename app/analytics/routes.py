import json
import re
from datetime import datetime, timedelta
from flask import render_template, flash, jsonify, request, redirect, url_for, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.analytics import analytics_bp
from app.analytics.forms import ReportWizardForm
from app.analytics.services import AnalyticsService
from app.analytics.exporters import export_to_csv, export_to_excel, export_to_pdf, send_report_email_async
from app.binnacle.services import BinnacleService
from app.binnacle.types import AuditModule, AuditAction, AuditStatus
from app.decorators import role_required, check_permissions
from app.models import Request, Training, Municipality, Parish

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

@analytics_bp.route('/indicadores', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
@check_permissions('view_statistics')
def indicators_view():
    """
    Vista 2: Consola Analítica "Indicadores de Gestión".
    """
    try:
        context = AnalyticsService.get_indicators_initial_context(current_user)
        return render_template(
            'analytics/indicators.html',
            ctx=context,
            initial_data_json=json.dumps(context['initial_data'])
        )
    except Exception as e:
        print(f"[ERROR analytics.indicators_view]: {e}")
        flash("Ocurrió un error al cargar la consola de indicadores de gestión.", "danger")
        return redirect(url_for('analytics.index'))

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

@analytics_bp.route('/reportes', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
@check_permissions('view_statistics')
def reports_wizard():
    """
    Vista 3: Asistente Wizard "Generar Reportes" (Paso 1 y Paso 2).
    """
    try:
        form = ReportWizardForm()
        context = AnalyticsService.get_wizard_initial_context(current_user, request.args)
        return render_template(
            'analytics/reports_wizard.html',
            form=form,
            ctx=context
        )
    except Exception as e:
        print(f"[ERROR analytics.reports_wizard]: {e}")
        flash("Ocurrió un error al cargar el generador de reportes.", "danger")
        return redirect(url_for('analytics.index'))

@analytics_bp.route('/api/geo/municipalities/<int:state_id>', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
def get_geo_municipalities(state_id):
    """
    Retorna los municipios de un estado para la cascada del wizard.
    Si es state_admin, se valida que pertenezca a su jurisdicción.
    """
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    if user_role == 'state_admin':
        from app.dashboard.services import get_user_state_info
        state_info = get_user_state_info(current_user)
        if not state_info or state_info.get('state_id') != state_id:
            return jsonify([]), 403

    municipalities = Municipality.query.filter_by(state_id=state_id).order_by(Municipality.name).all()
    return jsonify([{'id': m.id, 'name': m.name} for m in municipalities])

@analytics_bp.route('/api/geo/parishes/<int:municipality_id>', methods=['GET'])
@login_required
@role_required('super_admin', 'state_admin')
def get_geo_parishes(municipality_id):
    """
    Retorna las parroquias de un municipio para la cascada del wizard.
    Si es state_admin, se valida que pertenezca a su estado asignado.
    """
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    municipality = Municipality.query.get(municipality_id)
    if not municipality:
        return jsonify([])

    if user_role == 'state_admin':
        from app.dashboard.services import get_user_state_info
        state_info = get_user_state_info(current_user)
        if not state_info or state_info.get('state_id') != municipality.state_id:
            return jsonify([]), 403

    parishes = Parish.query.filter_by(municipality_id=municipality_id).order_by(Parish.name).all()
    return jsonify([{'id': p.id, 'name': p.name} for p in parishes])


@analytics_bp.route('/export', methods=['POST'])
@login_required
@role_required('super_admin', 'state_admin')
@check_permissions('view_statistics')
def export_report():
    """
    Endpoint principal para generar y despachar el reporte configurado en el Wizard.
    Aplica blindaje territorial Anti-IDOR, sanitización y auditoría forense.
    """
    # Capturar datos del Wizard (Paso 1 y 2)
    report_name = request.form.get('report_name', '').strip() or "Reporte_Institucional_SAGES"
    report_type = request.form.get('report_type', 'gestion_general')
    export_format = request.form.get('export_format', 'pdf').lower()
    delivery_method = request.form.get('delivery_method', 'local').lower()

    include_user = request.form.get('include_user_data') in ['y', 'true', 'True', True, 'on']
    include_req = request.form.get('include_request_details') in ['y', 'true', 'True', True, 'on']
    include_metrics = request.form.get('include_metrics') in ['y', 'true', 'True', True, 'on']

    form_config = {
        'report_type': report_type,
        'include_user_data': include_user,
        'include_request_details': include_req,
        'include_metrics': include_metrics
    }

    # Capturar filtros de segmentación de la barra lateral
    filter_params = {
        'state_id': request.form.get('state_id', type=int),
        'municipality_id': request.form.get('municipality_id', type=int),
        'parish_id': request.form.get('parish_id', type=int),
        'institution_scope_id': request.form.get('institution_scope_id', type=int),
        'educational_level_id': request.form.get('educational_level_id', type=int),
        'month': request.form.get('month', type=int),
        'date_from': request.form.get('date_from', ''),
        'date_to': request.form.get('date_to', '')
    }

    # 1. Sanitizar el nombre del archivo resultante
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', report_name.strip())
    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M')

    try:
        # 2. Extraer datos estructurados con blindaje territorial Anti-IDOR y matrices ejecutivas
        headers, data_rows, report_meta = AnalyticsService.build_export_dataset(current_user, form_config, filter_params)

        # 3. Compilación binaria en memoria según formato
        user_display_name = f"{current_user.person.first_name} {current_user.person.last_name}" if current_user.person else "Administrador"

        if export_format == 'xlsx':
            file_name = f"{safe_name}_{timestamp_str}.xlsx"
            mem_file, mimetype, download_name = export_to_excel(headers, data_rows, sheet_title="SAGES", filename=file_name)
        elif export_format == 'csv':
            file_name = f"{safe_name}_{timestamp_str}.csv"
            mem_file, mimetype, download_name = export_to_csv(headers, data_rows, filename=file_name)
        else:  # PDF por defecto
            file_name = f"{safe_name}_{timestamp_str}.pdf"
            mem_file, mimetype, download_name = export_to_pdf(
                headers, data_rows, title=report_name, filename=file_name,
                user_name=user_display_name, report_meta=report_meta
            )

        # 4. Trazabilidad en Bitácora Institucional (Auditoría Forense)
        BinnacleService.create_log_entry(
            module=AuditModule.REQUESTS.value,
            action_type=AuditAction.DESCARGA_REGISTRO.value,
            description=f"Reporte emitido: '{report_name}' | Formato: {export_format.upper()} | Canal: {delivery_method.upper()}",
            target_table='sages.requests',
            status=AuditStatus.COMPLETADO.value
        )

        # 5. Despacho según el método elegido
        if delivery_method == 'email':
            user_email = current_user.person.email if current_user.person else None
            if not user_email:
                return jsonify({'success': False, 'message': 'El usuario autenticado no posee correo institucional registrado.'}), 400

            app_obj = current_app._get_current_object()
            send_report_email_async(
                app=app_obj,
                to_email=user_email,
                user_name=user_display_name,
                report_title=report_name,
                file_bytes=mem_file,
                filename=download_name,
                mimetype=mimetype
            )
            return jsonify({
                'success': True,
                'message': f'El reporte "{report_name}" ha sido generado y enviado a su correo ({user_email}).'
            }), 200

        else:
            # Descarga directa en el navegador
            return send_file(
                mem_file,
                mimetype=mimetype,
                as_attachment=True,
                download_name=download_name
            )

    except Exception as e:
        print(f"[ERROR export_report]: {e}")
        return jsonify({'success': False, 'message': f'Error al compilar el reporte: {str(e)}'}), 500

