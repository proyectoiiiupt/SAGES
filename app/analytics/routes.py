import json
import re
from datetime import datetime, timedelta
from flask import render_template, flash, jsonify, request, redirect, url_for, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.extensions import limiter
from app.analytics import analytics_bp
from app.analytics.forms import ReportWizardForm, IndicatorsFilterForm
from app.analytics.services import AnalyticsService
from app.analytics.exporters import export_to_csv, export_to_excel, export_to_pdf, send_report_email_async
from app.binnacle.services import BinnacleService
from app.binnacle.types import AuditModule, AuditAction, AuditStatus
from app.decorators import role_required, check_permissions
from app.models import Request, Training, Municipality, Parish
from app.dashboard.services import get_user_state_info
from app.notifications.services import NotificationService
from app.notifications.enums import NotificationEvent, NotificationType

# ---------------------------------------------------------------------------
# Helpers Privados de Auditoría y Seguridad
# ---------------------------------------------------------------------------

def _notify_idor_attempt(actor_user, actor_state_id, target_state_id, endpoint_name: str):
    """Emite una alerta de seguridad (DANGER) al Super Admin ante intentos de IDOR territorial."""
    try:
        actor_name = "Usuario"
        if actor_user and hasattr(actor_user, 'person') and actor_user.person:
            p = actor_user.person
            actor_name = f"{p.first_name or ''} {p.last_name or ''}".strip() or getattr(actor_user, 'user_name', 'Usuario')
        elif actor_user:
            actor_name = getattr(actor_user, 'user_name', 'Usuario')

        NotificationService.notify_role(
            role_name="super_admin",
            event=NotificationEvent.ANALYTICS_SECURITY_IDOR_ATTEMPT,
            context={
                "actor_name": actor_name,
                "actor_id": actor_user.id if actor_user else 0,
                "actor_state": str(actor_state_id or "Sin Sede"),
                "target_state": str(target_state_id or "Nacional/Otro"),
                "endpoint_name": endpoint_name
            },
            severity_override=NotificationType.DANGER,
            redirect_url="/analytics/",
            action_text="Auditar Usuario"
        )
    except Exception as notif_err:
        current_app.logger.warning(f"Error enviando alerta IDOR: {notif_err}")

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


@analytics_bp.route('/api/indicators-data', methods=['POST'])
@login_required
@role_required('super_admin', 'state_admin')
@check_permissions('view_statistics')
@limiter.limit("30 per minute", key_func=lambda: str(current_user.id))
def indicators_data_api():
    """
    Endpoint AJAX principal consumido por el botón [Calcular Indicadores].
    Recibe JSON, valida campos, ejecuta agregaciones seguras y retorna las series de Chart.js.
    """
    payload = request.get_json(silent=True) or {}
    form = IndicatorsFilterForm.from_json(payload)

    if not form.validate():
        errors = [err for fld_errs in form.errors.values() for err in fld_errs]
        return jsonify({
            'success': False,
            'message': errors[0] if errors else 'Parámetros de filtrado inválidos.'
        }), 400

    try:
        clean_filters = form.get_clean_filters()

        # Detección y alerta de intento IDOR territorial
        user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
        if user_role == 'state_admin':
            st_info = get_user_state_info(current_user)
            user_state_id = st_info.get('state_id') if st_info else None
            req_st = clean_filters.get('state_id')
            if req_st is not None and user_state_id and int(req_st) != user_state_id:
                _notify_idor_attempt(current_user, user_state_id, req_st, "/analytics/api/indicators-data")

        data = AnalyticsService.calculate_filtered_indicators(current_user, clean_filters)
        return jsonify({
            'success': True,
            'data': data
        }), 200

    except PermissionError as pe:
        return jsonify({'success': False, 'message': str(pe)}), 403
    except Exception as e:
        current_app.logger.error(f"[ERROR indicators_data_api]: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Ocurrió un error al recalcular los indicadores.'
        }), 500

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
        state_info = get_user_state_info(current_user)
        if not state_info or state_info.get('state_id') != state_id:
            _notify_idor_attempt(
                current_user,
                state_info.get('state_id') if state_info else "Sin Sede",
                state_id,
                f"/analytics/api/geo/municipalities/{state_id}"
            )
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
    municipality = db.session.get(Municipality, municipality_id)
    if not municipality:
        return jsonify([])

    if user_role == 'state_admin':
        state_info = get_user_state_info(current_user)
        if not state_info or state_info.get('state_id') != municipality.state_id:
            _notify_idor_attempt(
                current_user,
                state_info.get('state_id') if state_info else "Sin Sede",
                municipality.state_id,
                f"/analytics/api/geo/parishes/{municipality_id}"
            )
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

    # Alerta IDOR preventiva si un state_admin manipula el formulario
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    if user_role == 'state_admin':
        state_info = get_user_state_info(current_user)
        user_state_id = state_info.get('state_id') if state_info else None
        req_state = filter_params.get('state_id')
        if req_state is not None and user_state_id and int(req_state) != user_state_id:
            _notify_idor_attempt(current_user, user_state_id, req_state, "/analytics/export")

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
                mimetype=mimetype,
                user_id=current_user.id
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


@analytics_bp.route('/api/export-indicators', methods=['POST'])
@login_required
@role_required('super_admin', 'state_admin')
@check_permissions('view_statistics')
@limiter.limit("20 per minute", key_func=lambda: str(current_user.id))
def export_indicators_api():
    """
    Endpoint dedicado para la exportación directa de Indicadores de Gestión desde la Consola Analítica (Vista 2).
    Soporta formatos: Excel (.xlsx), CSV (.csv) y PDF (.pdf), con doble vía de entrega (descarga local o correo).
    """
    payload = request.get_json(silent=True) or request.form.to_dict() or {}

    export_format = str(payload.get('export_format', 'xlsx')).lower().strip()
    if export_format not in ['xlsx', 'csv', 'pdf']:
        export_format = 'xlsx'

    delivery_method = str(payload.get('delivery_method', 'local')).lower().strip()
    if delivery_method not in ['local', 'email']:
        delivery_method = 'local'

    form = IndicatorsFilterForm.from_json(payload)
    if not form.validate():
        first_error = next(iter(form.errors.values()))[0] if form.errors else "Filtros inválidos"
        return jsonify({'success': False, 'message': f"Error de validación: {first_error}"}), 400

    clean_filters = form.get_clean_filters()

    # Alerta IDOR preventiva
    user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
    if user_role == 'state_admin':
        state_info = get_user_state_info(current_user)
        user_state_id = state_info.get('state_id') if state_info else None
        req_state = clean_filters.get('state_id')
        if req_state is not None and user_state_id and int(req_state) != user_state_id:
            _notify_idor_attempt(current_user, user_state_id, req_state, "/analytics/api/export-indicators")

    try:
        # Calcular los indicadores con blindaje territorial Anti-IDOR
        indicators_data = AnalyticsService.calculate_filtered_indicators(current_user, clean_filters)

        timeline_labels = indicators_data.get('labels', [])
        generadas_series = indicators_data.get('generadas', [])
        atendidas_series = indicators_data.get('atendidas', [])
        summary = indicators_data.get('summary', {})

        # 1. Estructuración tabular de los datos
        headers = ["Hito / Fecha", "Solicitudes Generadas", "Solicitudes Atendidas", "Tasa de Cumplimiento (%)"]
        data_rows = []
        for i in range(len(timeline_labels)):
            g = generadas_series[i] if i < len(generadas_series) else 0
            a = atendidas_series[i] if i < len(atendidas_series) else 0
            rate = f"{(a / g * 100):.1f}%" if g > 0 else "0.0%"
            data_rows.append([timeline_labels[i], g, a, rate])

        tot_g = summary.get('total_generadas', 0)
        tot_a = summary.get('total_atendidas', 0)
        tot_rate = summary.get('tasa_resolucion', '0.0%')
        data_rows.append(["TOTAL CONSOLIDADO", tot_g, tot_a, tot_rate])

        # 2. Metadatos de presentación
        user_role = current_user.roles_assoc[0].role.name if current_user.roles_assoc else 'applicant'
        state_info = get_user_state_info(current_user) if user_role == 'state_admin' else None
        scope_label = state_info['state_name'] if state_info else "Consolidado Nacional"

        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M')
        base_name = f"Indicadores_Gestion_{scope_label.replace(' ', '_')}"
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', base_name)
        report_title = "Indicadores de Gestión - Demanda vs Cobertura"

        report_meta = {
            'subtitle_scope': f"Ámbito: {scope_label} | Corte: {clean_filters.get('time_mode', 'Mes')}",
            'kpis': [
                {'label': 'Solicitudes Generadas', 'value': str(tot_g)},
                {'label': 'Solicitudes Atendidas', 'value': str(tot_a)},
                {'label': 'Tasa de Cumplimiento', 'value': str(tot_rate)},
                {'label': 'Hitos Temporales', 'value': str(len(timeline_labels))}
            ],
            'summary_title': '1. Matriz de Serie Temporal (Demanda vs. Respuesta Operativa)',
            'summary_headers': headers,
            'summary_rows': data_rows,
            'summary_weights': [2.0, 1.5, 1.5, 1.5],
            'center_cols_summary': {"Solicitudes Generadas", "Solicitudes Atendidas", "Tasa de Cumplimiento (%)"},
            'detail_title': '2. Relación de Indicadores por Hito',
            'pdf_headers': headers,
            'pdf_rows': data_rows,
            'pdf_weights': [2.0, 1.5, 1.5, 1.5],
            'center_cols_detail': {"Solicitudes Generadas", "Solicitudes Atendidas", "Tasa de Cumplimiento (%)"}
        }

        user_display_name = f"{current_user.person.first_name} {current_user.person.last_name}" if getattr(current_user, 'person', None) else "Administrador"

        # 3. Serialización binaria según formato
        if export_format == 'xlsx':
            file_name = f"{safe_name}_{timestamp_str}.xlsx"
            mem_file, mimetype, download_name = export_to_excel(headers, data_rows, sheet_title="Indicadores", filename=file_name)
        elif export_format == 'csv':
            file_name = f"{safe_name}_{timestamp_str}.csv"
            mem_file, mimetype, download_name = export_to_csv(headers, data_rows, filename=file_name)
        else: # pdf
            file_name = f"{safe_name}_{timestamp_str}.pdf"
            mem_file, mimetype, download_name = export_to_pdf(
                headers, data_rows, title=report_title,
                filename=file_name, user_name=user_display_name, report_meta=report_meta
            )

        # 4. Trazabilidad en Bitácora
        BinnacleService.create_log_entry(
            module=AuditModule.REQUESTS.value,
            action_type=AuditAction.DESCARGA_REGISTRO.value,
            description=f"Exportación directa de indicadores: '{file_name}' | Formato: {export_format.upper()} | Canal: {delivery_method.upper()}",
            target_table='sages.requests',
            status=AuditStatus.COMPLETADO.value
        )

        # 5. Despacho según canal
        if delivery_method == 'email':
            user_email = current_user.person.email if current_user.person else None
            if not user_email:
                return jsonify({'success': False, 'message': 'El usuario autenticado no posee correo institucional registrado.'}), 400

            app_obj = current_app._get_current_object()
            send_report_email_async(
                app=app_obj,
                to_email=user_email,
                user_name=user_display_name,
                report_title=report_title,
                file_bytes=mem_file,
                filename=download_name,
                mimetype=mimetype,
                user_id=current_user.id
            )
            return jsonify({
                'success': True,
                'message': f'El reporte de indicadores ha sido generado y enviado satisfactoriamente a su correo institucional ({user_email}).'
            }), 200

        # Descarga binaria directa
        return send_file(
            mem_file,
            mimetype=mimetype,
            as_attachment=True,
            download_name=download_name
        )

    except PermissionError as pe:
        return jsonify({'success': False, 'message': str(pe)}), 403
    except Exception as e:
        current_app.logger.error(f"[ERROR export_indicators_api]: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Ocurrió un error al compilar el archivo de exportación de indicadores.'
        }), 500

