from datetime import datetime, timezone, timedelta
from sqlalchemy import func, case, and_
from app.extensions import db
from app.models.request_model import Request
from app.models.status_model import Status
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.institution_model import Institution
from app.models.parish_model import Parish
from app.models.municipality_model import Municipality
from app.models.state_model import State
from app.models.training_model import Training
from app.dashboard.services import get_user_state_info

class AnalyticsService:
    @staticmethod
    def get_scoped_requests_query(user, state_id=None):
        """
        Genera la consulta base sobre requests aplicando aislamiento territorial RBAC.
        Anti-IDOR: Si es state_admin, el state_id es incondicionalmente el de su sede.
        """
        query = db.session.query(Request).select_from(Request)\
            .join(Request.institutional_staff)\
            .join(InstitutionalStaff.institution)\
            .join(Institution.parish)\
            .join(Parish.municipality)\
            .join(Municipality.state)

        user_role = user.roles_assoc[0].role.name if user.roles_assoc else 'applicant'

        if user_role == 'state_admin':
            state_info = get_user_state_info(user)
            authorized_state = state_info['state_id'] if state_info else 0
            query = query.filter(State.id == authorized_state)
        elif user_role == 'super_admin' and state_id:
            query = query.filter(State.id == state_id)

        return query

    @staticmethod
    def get_dashboard_metrics(user, state_id=None):
        """
        Calcula todos los conjuntos de datos necesarios para la Vista 1 (Tablero Ejecutivo).
        """
        now = datetime.now(timezone.utc)
        hace_28_dias = now - timedelta(days=28)
        hace_56_dias = now - timedelta(days=56)

        base_q = AnalyticsService.get_scoped_requests_query(user, state_id)
        

        # 1. KPI: Últimos 28 días vs ciclo anterior
        req_ultimos_28 = base_q.filter(Request.created_at >= hace_28_dias).count()
        req_ciclo_previo = base_q.filter(
            and_(Request.created_at >= hace_56_dias, Request.created_at < hace_28_dias)
        ).count()

        diferencial_pct = 0.0
        if req_ciclo_previo > 0:
            diferencial_pct = round(((req_ultimos_28 - req_ciclo_previo) / req_ciclo_previo) * 100, 1)

        # 2. Distribución de Estatus (Gráfico Donut)
        # STAT-007: Completado/Aprobada | STAT-006: En Proceso | STAT-003, STAT-004: Pendientes
        status_data = base_q.join(Request.status).with_entities(
            func.count(case((Status.status_code == 'STAT-007', Request.id))).label('aprobadas'),
            func.count(case((Status.status_code == 'STAT-006', Request.id))).label('en_proceso'),
            func.count(case((Status.status_code.in_(['STAT-003', 'STAT-004']), Request.id))).label('pendientes')
        ).first()

        donut_dataset = {
            'aprobadas': status_data.aprobadas or 0,
            'en_proceso': status_data.en_proceso or 0,
            'pendientes': status_data.pendientes or 0,
            'total': (status_data.aprobadas or 0) + (status_data.en_proceso or 0) + (status_data.pendientes or 0)
        }

        # 3. Evolución de Solicitudes en el Tiempo (Gráfico de Líneas estilo ventas/mercado)
        timeline_q = base_q.join(Request.status)\
            .filter(Request.created_at >= hace_28_dias)\
            .with_entities(
                func.date_trunc('day', Request.created_at).label('fecha_dia'),
                func.count(case((Status.status_code == 'STAT-007', Request.id))).label('aprobadas'),
                func.count(case((Status.status_code == 'STAT-006', Request.id))).label('en_proceso'),
                func.count(case((Status.status_code.in_(['STAT-003', 'STAT-004']), Request.id))).label('pendientes')
            )\
            .group_by('fecha_dia')\
            .order_by('fecha_dia').all()

        line_labels = [row.fecha_dia.strftime('%d %b') if row.fecha_dia else '' for row in timeline_q]
        line_aprobadas = [row.aprobadas for row in timeline_q]
        line_en_proceso = [row.en_proceso for row in timeline_q]
        line_pendientes = [row.pendientes for row in timeline_q]

        # Si hay pocos registros o es inicio de mes, asegurar al menos etiquetas base
        if not line_labels:
            line_labels = [(hace_28_dias + timedelta(days=i * 5)).strftime('%d %b') for i in range(6)]
            line_aprobadas = [0] * len(line_labels)
            line_en_proceso = [0] * len(line_labels)
            line_pendientes = [0] * len(line_labels)

        lines_dataset = {
            'labels': line_labels,
            'aprobadas': line_aprobadas,
            'en_proceso': line_en_proceso,
            'pendientes': line_pendientes
        }

        # 4. Distribución por Temas Formativos (Gráfico de Barras Horizontales)
        trainings_q = base_q.join(Request.training)\
            .with_entities(
                Training.name,
                func.count(Request.id).label('total_solicitudes')
            )\
            .group_by(Training.name)\
            .order_by(func.count(Request.id).desc())\
            .limit(6).all()

        bar_labels = [row.name for row in trainings_q]
        bar_values = [row.total_solicitudes for row in trainings_q]

        bars_dataset = {
            'labels': bar_labels,
            'data': bar_values
        }

        # Información territorial de contexto para la vista
        user_role = user.roles_assoc[0].role.name if user.roles_assoc else 'applicant'
        state_info = get_user_state_info(user) if user_role == 'state_admin' else None
        jurisdiction_label = f"Estado {state_info['state_name']}" if state_info else "Nivel Nacional (Consolidado)"

        return {
            'kpi_28_dias': req_ultimos_28,
            'diferencial_pct': diferencial_pct,
            'jurisdiction_label': jurisdiction_label,
            'donut': donut_dataset,
            'lines': lines_dataset,
            'bars': bars_dataset
        }