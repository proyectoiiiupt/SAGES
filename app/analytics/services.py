from collections import defaultdict
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, case, and_, extract
from app.extensions import db
from app.models.request_model import Request
from app.models.status_model import Status
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.institution_model import Institution
from app.models.parish_model import Parish
from app.models.municipality_model import Municipality
from app.models.state_model import State
from app.models.training_model import Training
from app.models.institution_type_model import InstitutionType
from app.models.institution_scope_model import InstitutionScope
from app.models.educational_level_model import EducationalLevel
from app.models.institution_level_model import InstitutionLevel
from app.models.request_planning_model import RequestPlanning
from app.dashboard.services import get_user_state_info
from app.binnacle.services import BinnacleService
from app.binnacle.types import AuditModule, AuditAction, AuditStatus

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

    @staticmethod
    def get_wizard_initial_context(user, request_args):
        """
        [US-55 + Parámetros de Blindaje Territorial de US-56]
        Prepara el contexto de filtros laterales y seguridad para el Asistente Wizard.
        """
        user_role = user.roles_assoc[0].role.name if user.roles_assoc else 'applicant'
        state_info = get_user_state_info(user) if user_role == 'state_admin' else None

        # 1. Blindaje territorial de catálogos
        if user_role == 'super_admin':
            states = State.query.order_by(State.name).all()
        else:
            states = [State.query.get(state_info['state_id'])] if state_info else []

        inst_types = InstitutionType.query.order_by(InstitutionType.name).all()
        inst_scopes = InstitutionScope.query.order_by(InstitutionScope.name).all()
        edu_levels = EducationalLevel.query.order_by(EducationalLevel.name).all()

        # 2. Captura de filtros pre-seleccionados transferidos desde la Vista 2
        preselected = {
            'state_id': state_info['state_id'] if user_role == 'state_admin' else request_args.get('state_id', type=int),
            'municipality_id': request_args.get('municipality_id', type=int),
            'parish_id': request_args.get('parish_id', type=int),
            'institution_scope_id': request_args.get('institution_scope_id', type=int),
            'educational_level_id': request_args.get('educational_level_id', type=int),
            'month': request_args.get('month', type=int),
            'date_from': request_args.get('date_from', ''),
            'date_to': request_args.get('date_to', '')
        }

        return {
            'user_role': user_role,
            'user_state': state_info,
            'states': states,
            'institution_types': inst_types,
            'institution_scopes': inst_scopes,
            'educational_levels': edu_levels,
            'preselected': preselected
        }

    @staticmethod
    def get_scoped_base_query(user, filters):
        """
        Construye la consulta base asegurando el aislamiento por rol (Anti-IDOR)
        y aplicando los filtros institucionales y temporales de la barra lateral.
        """
        filters = filters or {}
        query = db.session.query(Request).select_from(Request)\
            .join(Request.institutional_staff)\
            .join(InstitutionalStaff.institution)\
            .join(Institution.parish)\
            .join(Parish.municipality)\
            .join(Municipality.state)

        user_role = user.roles_assoc[0].role.name if user.roles_assoc else 'applicant'

        # 1. Blindaje territorial Anti-IDOR
        if user_role == 'state_admin':
            state_info = get_user_state_info(user)
            authorized_state_id = state_info['state_id'] if state_info else 0
            query = query.filter(State.id == authorized_state_id)
        elif user_role == 'super_admin':
            if filters.get('state_id'):
                query = query.filter(State.id == filters['state_id'])
        else:
            return query.filter(Request.id == 0)

        # 2. Filtros geográficos en cascada
        if filters.get('municipality_id'):
            query = query.filter(Municipality.id == filters['municipality_id'])
        if filters.get('parish_id'):
            query = query.filter(Parish.id == filters['parish_id'])

        # 3. Filtros de Clasificación Institucional (SR-F-023)
        if filters.get('institution_scope_id'):
            query = query.filter(Institution.institution_scope_id == filters['institution_scope_id'])
        if filters.get('educational_level_id'):
            query = query.join(Institution.institution_levels)\
                         .filter(InstitutionLevel.educational_level_id == filters['educational_level_id'])

        # 4. Filtros Temporales (Rango de fechas o Mes seleccionado)
        if filters.get('date_from'):
            query = query.filter(Request.created_at >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(Request.created_at <= f"{filters['date_to']} 23:59:59")
        elif filters.get('month') and not filters.get('date_from'):
            try:
                query = query.filter(extract('month', Request.created_at) == int(filters['month']))
            except (ValueError, TypeError):
                pass

        return query

    @staticmethod
    def build_export_dataset(user, form_data, filters):
        """
        Construye:
        1) headers y data_rows (columnas atómicas para Excel y CSV).
        2) report_meta (KPIs, Matriz Consolidada Sección 1 y Tabla Estilizada Sección 2 para PDF).
        """
        report_type = form_data.get('report_type', 'gestion_general')
        include_user = form_data.get('include_user_data', True)
        include_req = form_data.get('include_request_details', True)
        include_metrics = form_data.get('include_metrics', True)

        user_role = user.roles_assoc[0].role.name if user.roles_assoc else 'applicant'
        state_info = get_user_state_info(user) if user_role == 'state_admin' else None
        scope_label = state_info['state_name'] if state_info else "Consolidado Nacional / Filtrado"

        # ── CASO ESPECIAL: REPORTE 4 (AUDITORÍA DE USUARIOS Y BITÁCORA) ──
        if report_type == 'auditoria_usuarios':
            from app.models.binnacle_model import Binnacle
            bin_q = db.session.query(Binnacle).order_by(Binnacle.created_at.desc())
            if filters.get('date_from'):
                bin_q = bin_q.filter(Binnacle.created_at >= filters['date_from'])
            if filters.get('date_to'):
                bin_q = bin_q.filter(Binnacle.created_at <= f"{filters['date_to']} 23:59:59")
            elif filters.get('month') and not filters.get('date_from'):
                try:
                    bin_q = bin_q.filter(extract('month', Binnacle.created_at) == int(filters['month']))
                except (ValueError, TypeError):
                    pass

            logs = bin_q.limit(200).all()
            headers = [
                'ID Evento', 'Fecha y Hora', 'Módulo', 'Acción Ejecutada',
                'Tabla Objetivo', 'Usuario Operador', 'Cédula Operador',
                'Rol Institucional', 'Jurisdicción', 'Descripción de la Operación', 'Estatus'
            ]
            data_rows = []
            pdf_rows = []
            action_Groups = defaultdict(lambda: {'table': '', 'super': 0, 'state': 0, 'total': 0})
            operators_set = set()
            completed_logs = 0

            for lg in logs:
                u = getattr(lg, 'user', None)
                p = getattr(u, 'person', None) if u else None
                u_name = f"{p.first_name} {p.last_name}" if p else "Sistema / Operador"
                u_ci = f"{p.identification_type}-{p.identification_number}" if p else "N/A"
                r_name = u.roles_assoc[0].role.name if (u and u.roles_assoc) else "super_admin"
                rol_label = "Super Administrador" if r_name == 'super_admin' else "Administrador Estadal"
                jur_label = "Nacional" if r_name == 'super_admin' else scope_label
                ev_code = f"BIN-{lg.id:05d}" if getattr(lg, 'id', None) else "BIN-SAGES"
                dt_str = lg.created_at.strftime('%Y-%m-%d %H:%M') if getattr(lg, 'created_at', None) else "S/F"
                act_name = getattr(lg, 'action_type', 'OPERACION')
                tbl_name = getattr(lg, 'target_table', 'sages.requests') or 'sages.requests'
                st_name = getattr(lg, 'status', 'COMPLETADO') or 'COMPLETADO'
                desc_txt = getattr(lg, 'description', '') or ''

                operators_set.add(u_name)
                if 'COMPLET' in st_name.upper():
                    completed_logs += 1

                grp = action_Groups[act_name]
                grp['table'] = tbl_name
                if r_name == 'super_admin':
                    grp['super'] += 1
                else:
                    grp['state'] += 1
                grp['total'] += 1

                data_rows.append([ev_code, dt_str, getattr(lg, 'module', 'REQUESTS'), act_name, tbl_name, u_name, u_ci, rol_label, jur_label, desc_txt, st_name])
                pdf_rows.append([
                    f"{ev_code}\n{dt_str}",
                    f"{getattr(lg, 'module', 'REQUESTS')}\n{act_name}",
                    tbl_name,
                    f"{u_name}\nC.I: {u_ci}",
                    f"{rol_label}\n{jur_label}",
                    desc_txt,
                    st_name
                ])

            sum_rows = []
            for act_key, g in action_Groups.items():
                sum_rows.append([act_key, g['table'], str(g['super']), str(g['state']), str(g['total']), "100% Auditado"])
            sum_rows.append([
                "Total Operaciones Auditadas", "Esquema sages.*",
                str(sum(x['super'] for x in action_Groups.values())),
                str(sum(x['state'] for x in action_Groups.values())),
                str(len(logs)), "Sin Incidencias"
            ])

            pct_ok = round((completed_logs / len(logs) * 100), 1) if logs else 100.0
            report_meta = {
                'report_type': report_type,
                'include_metrics': include_metrics,
                'subtitle_scope': scope_label,
                'force_page_size': 'letter',
                'kpi_headers': ["EVENTOS AUDITADOS", "OPERACIONES EXITOSAS", "OPERADORES ACTIVOS", "FUENTE DE TRAZABILIDAD"],
                'kpi_values': [f"{len(logs)} Registros Forenses", f"{completed_logs} ({pct_ok}%)", f"{len(operators_set)} Administradores", "Bitácora (sages.binnacle)"],
                'summary_title': "1. Resumen de Actividad Operativa por Tipo de Acción y Rol Institucional",
                'summary_headers': ["Tipo de Acción en Bitácora", "Tabla Objetivo", "Super Administrador", "Administrador Estadal", "Total Eventos", "Estatus de Auditoría"],
                'summary_rows': sum_rows,
                'summary_weights': [2.1, 1.4, 1.0, 1.0, 0.8, 1.3],
                'center_cols_summary': {"Tabla Objetivo", "Super Administrador", "Administrador Estadal", "Total Eventos", "Estatus de Auditoría"},
                'detail_title': "2. Bitácora Cronológica de Eventos y Trazabilidad por Operador (Formato Carta Horizontal)",
                'pdf_headers': ["ID Evento / Fecha", "Módulo / Acción Ejecutada", "Tabla Objetivo", "Operador Responsable", "Rol y Jurisdicción", "Detalle Técnico de la Operación", "Resultado"],
                'pdf_rows': pdf_rows,
                'pdf_weights': [1.05, 1.30, 1.45, 1.15, 1.20, 2.35, 0.85],
                'center_cols_detail': {"ID Evento / Fecha", "Tabla Objetivo", "Resultado"}
            }
            return headers, data_rows, report_meta

        # ── REPORTES 1, 2 Y 3 (BASADOS EN SAGES.REQUESTS) ──
        from app.models.request_justification_model import RequestJustification
        from app.models.reason_model import Reason
        from app.models.request_planning_model import RequestPlanning

        query = AnalyticsService.get_scoped_base_query(user, filters)\
            .join(Request.status)\
            .join(Request.training)\
            .join(Training.training_module)\
            .outerjoin(Request.plannings)

        if report_type == 'impacto_educativo':
            query = query.filter(Status.status_code == 'STAT-007')
        elif report_type == 'retrasos_ans':
            query = query.filter(RequestPlanning.is_exceeded == True)\
                         .outerjoin(Request.justifications)\
                         .outerjoin(RequestJustification.reason)

        records = query.order_by(Request.created_at.desc()).all()

        # 1. Encabezados atómicos para Excel y CSV (15/16 columnas)
        headers = []
        if include_req:
            headers.extend(['Código Solicitud', 'Fecha Radicación', 'Módulo Rector', 'Tema Formativo'])
        headers.extend(['Plantel Educativo', 'Código DEA', 'Sector', 'Nivel Educativo', 'Estado', 'Municipio'])
        if include_user:
            headers.extend(['Cédula Solicitante', 'Nombre Representante', 'Cargo'])
        if include_metrics:
            if report_type == 'retrasos_ans':
                headers.extend(['Exceso ANS (Horas)', 'Motivo Tipificado', 'Justificación de Demora'])
            else:
                headers.extend(['Estatus Actual', 'Atendida'])

        # 2. Contadores para KPIs y Matrices Consolidadas (Sección 1)
        total_records = len(records)
        atendidas_count = 0
        publicos_count = 0
        privados_count = 0
        total_horas_exceso = 0
        planteles_set = set()
        niveles_set = set()

        status_matrix = defaultdict(lambda: {'pub': 0, 'priv': 0, 'total': 0})
        level_matrix = defaultdict(lambda: {'pub': 0, 'priv': 0, 'total': 0, 'mods': set()})
        reason_matrix = defaultdict(lambda: {'count': 0, 'hours': 0})

        data_rows = []
        pdf_rows = []

        for req in records:
            staff = req.institutional_staff
            inst = staff.institution if staff else None
            person = staff.person if staff else None
            parish = inst.parish if inst else None
            muni = parish.municipality if parish else None
            state = muni.state if muni else None
            planning = req.plannings[0] if req.plannings else None

            edu_level_name = 'Universitario'
            if inst and hasattr(inst, 'institution_levels') and inst.institution_levels:
                first_lvl = inst.institution_levels[0]
                if hasattr(first_lvl, 'educational_level') and first_lvl.educational_level:
                    edu_level_name = first_lvl.educational_level.name
            niveles_set.add(edu_level_name)

            inst_name = inst.institution_name if inst else 'N/A'
            dea_code = inst.plantel_code if inst else 'N/A'
            planteles_set.add(dea_code)

            scope_name = inst.institution_scope.name if inst and inst.institution_scope else 'Público'
            is_priv = 'priv' in scope_name.lower()
            if is_priv:
                privados_count += 1
            else:
                publicos_count += 1

            st_name = req.status.status_name if req.status else 'Nuevo'
            is_attended = bool(planning and planning.attended) or (req.status and req.status.status_code == 'STAT-007')
            if is_attended:
                atendidas_count += 1

            ex_hours = (planning.time_exceeded or 0) if planning else 0
            total_horas_exceso += ex_hours

            mod_name = req.training.training_module.name if req.training and req.training.training_module else 'N/A'
            tema_name = req.training.name if req.training else 'N/A'
            dt_str = req.created_at.strftime('%Y-%m-%d %H:%M') if req.created_at else 'S/F'
            ci_str = f"{person.identification_type}-{person.identification_number}" if person else 'N/A'
            rep_name = f"{person.first_name} {person.last_name}" if person else 'N/A'
            cargo_name = staff.position.name if staff and staff.position else 'Representante'
            state_name = state.name if state else 'N/A'
            muni_name = muni.name if muni else 'N/A'

            # Alimentar Matrices Consolidadas
            status_matrix[st_name]['pub' if not is_priv else 'priv'] += 1
            status_matrix[st_name]['total'] += 1

            level_matrix[edu_level_name]['pub' if not is_priv else 'priv'] += 1
            level_matrix[edu_level_name]['total'] += 1
            level_matrix[edu_level_name]['mods'].add(mod_name)

            just = req.justifications[0] if getattr(req, 'justifications', None) else None
            reason_name = just.reason.name if just and just.reason else 'Retraso Operativo'
            just_text = just.justification if just else 'Sin descargo registrado'
            reason_matrix[reason_name]['count'] += 1
            reason_matrix[reason_name]['hours'] += ex_hours

            # Fila atómica para Excel / CSV
            row = []
            if include_req:
                row.extend([req.request_code, dt_str, mod_name, tema_name])
            row.extend([inst_name, dea_code, scope_name, edu_level_name, state_name, muni_name])
            if include_user:
                row.extend([ci_str, rep_name, cargo_name])
            if include_metrics:
                if report_type == 'retrasos_ans':
                    row.extend([f"{ex_hours} h", reason_name, just_text])
                else:
                    row.extend([st_name, "SÍ" if is_attended else "NO"])
            data_rows.append(row)

            # Fila estilizada para PDF según el Tipo de Reporte
            if report_type == 'impacto_educativo':
                pdf_rows.append([
                    f"{req.request_code}\n{dt_str[:10]}",
                    f"{inst_name}\nCódigo DEA: {dea_code}",
                    f"{scope_name}\n{edu_level_name}",
                    mod_name,
                    tema_name,
                    f"{state_name}\nMun. {muni_name}",
                    f"{rep_name}\n{cargo_name} ({ci_str})"
                ])
            elif report_type == 'retrasos_ans':
                pdf_rows.append([
                    req.request_code, dt_str, f"{mod_name}\n{tema_name}",
                    inst_name, dea_code, f"{scope_name}\n{edu_level_name}",
                    f"{state_name}\nMun. {muni_name}", f"{rep_name}\n{ci_str} ({cargo_name})",
                    f"{ex_hours} h", reason_name, just_text
                ])
            else:
                pdf_row = []
                if include_req:
                    pdf_row.extend([req.request_code, dt_str, mod_name, tema_name])
                pdf_row.extend([inst_name, dea_code, f"{scope_name}\n{edu_level_name}", f"{state_name}\nMun. {muni_name}"])
                if include_user:
                    pdf_row.append(f"{rep_name}\n{ci_str} ({cargo_name})")
                if include_metrics:
                    pdf_row.extend([st_name, "SÍ" if is_attended else "NO"])
                pdf_rows.append(pdf_row)

        tasa_res = round((atendidas_count / total_records * 100), 1) if total_records > 0 else 0.0
        prom_exceso = round((total_horas_exceso / total_records), 1) if total_records > 0 else 0.0

        # 3. Configuración de la Matriz Consolidada (Sección 1) y Encabezados PDF (Sección 2)
        if report_type == 'impacto_educativo':
            sum_rows = []
            for lvl, d in level_matrix.items():
                pct = round((d['total'] / total_records * 100), 1) if total_records > 0 else 0.0
                sum_rows.append([lvl, str(d['pub']), str(d['priv']), str(d['total']), f"{pct}%", ", ".join(list(d['mods'])[:2])])
            sum_rows.append(["Total Impacto Socioeducativo", str(publicos_count), str(privados_count), str(total_records), "100.0%", "100% de Jornadas Ejecutadas"])

            report_meta = {
                'report_type': report_type, 'include_metrics': include_metrics, 'subtitle_scope': scope_label,
                'force_page_size': 'letter',
                'kpi_headers': ["JORNADAS EJECUTADAS (STAT-007)", "PLANTELES BENEFICIADOS", "COBERTURA PÚBLICA VS. PRIVADA", "NIVELES EDUCATIVOS ALCANZADOS"],
                'kpi_values': [f"{total_records} Actividades", f"{len(planteles_set)} Instituciones", f"Públicos: {publicos_count} | Privados: {privados_count}", ", ".join(list(niveles_set)[:3]) or "General"],
                'summary_title': "1. Matriz de Cobertura Socioeducativa por Nivel Educativo y Sector (Normativa SR-F-023)",
                'summary_headers': ["Nivel Educativo Oficial", "Jornadas en Sector Público", "Jornadas en Sector Privado", "Total Actividades Atendidas", "% de Cobertura", "Módulos UREE Impartidos"],
                'summary_rows': sum_rows,
                'summary_weights': [1.6, 1.1, 1.1, 1.2, 0.8, 2.2],
                'center_cols_summary': {"Jornadas en Sector Público", "Jornadas en Sector Privado", "Total Actividades Atendidas", "% de Cobertura"},
                'detail_title': "2. Detalle de Actividades Formativas Completadas en Comunidad (Formato Carta Horizontal)",
                'pdf_headers': ["Expediente / Cierre", "Plantel Educativo Beneficiado", "Sector / Nivel (SR-F-023)", "Módulo Rector UREE", "Tema Formativo Impartido", "Ubicación Territorial", "Enlace Institucional"],
                'pdf_rows': pdf_rows,
                'pdf_weights': [1.05, 1.95, 1.00, 1.35, 2.30, 1.00, 1.35],
                'center_cols_detail': {"Expediente / Cierre", "Sector / Nivel (SR-F-023)"}
            }

        elif report_type == 'retrasos_ans':
            sum_rows = []
            for r_name, d in reason_matrix.items():
                avg_h = round(d['hours'] / d['count'], 1) if d['count'] > 0 else 0.0
                pct = round((d['count'] / total_records * 100), 1) if total_records > 0 else 0.0
                sum_rows.append([r_name, str(d['count']), f"{d['hours']} h", f"{avg_h} h", f"{pct}%", "Expediente con justificación en bitácora"])
            sum_rows.append(["Total Consolidado de Retrasos ANS", str(total_records), f"{total_horas_exceso} h", f"{prom_exceso} h", "100.0%", "Auditoría conforme a SR-F-026"])

            report_meta = {
                'report_type': report_type, 'include_metrics': include_metrics, 'subtitle_scope': scope_label,
                'force_page_size': 'legal',
                'kpi_headers': ["EXPEDIENTES CON RETRASO ANS", "TIEMPO TOTAL / PROMEDIO EXCESO", "INCIDENCIA POR SECTOR", "NORMATIVA AUDITADA"],
                'kpi_values': [f"{total_records} Solicitudes", f"{total_horas_exceso} h ({prom_exceso} h Prom.)", f"Públicos: {publicos_count} | Privados: {privados_count}", "Plazos ANS (48-72h / 10 días)"],
                'summary_title': "1. Distribución de Incidencias por Motivo Tipificado del Catálogo (sages.reasons)",
                'summary_headers': ["Motivo Tipificado de Demora", "Expedientes Afectados", "Horas Acumuladas de Exceso", "Promedio de Demora", "% de Incidencia", "Impacto Operativo"],
                'summary_rows': sum_rows,
                'summary_weights': [2.0, 1.0, 1.1, 1.0, 0.8, 2.1],
                'center_cols_summary': {"Expedientes Afectados", "Horas Acumuladas de Exceso", "Promedio de Demora", "% de Incidencia"},
                'detail_title': "2. Auditoría Detallada de Expedientes con Exceso ANS y Descargos Registrados (Formato Oficio Horizontal)",
                'pdf_headers': ["Código Solicitud", "Fecha Radicación", "Módulo y Tema Formativo", "Plantel Educativo", "Código DEA", "Sector / Nivel", "Ubicación", "Solicitante (Cédula / Cargo)", "Exceso ANS", "Motivo Tipificado", "Justificación Formal de Demora (sages.request_justifications)"],
                'pdf_rows': pdf_rows,
                'pdf_weights': [1.10, 0.85, 1.80, 1.40, 0.75, 0.85, 0.90, 1.25, 0.65, 1.35, 2.55],
                'center_cols_detail': {"Código Solicitud", "Fecha Radicación", "Código DEA", "Sector / Nivel", "Exceso ANS"}
            }

        else:  # gestion_general
            sum_rows = []
            for st_key, d in status_matrix.items():
                pct = round((d['total'] / total_records * 100), 1) if total_records > 0 else 0.0
                sum_rows.append([st_key, str(d['pub']), str(d['priv']), str(d['total']), f"{pct}%", "Seguimiento operativo UREE"])
            sum_rows.append(["Total Consolidado del Periodo", str(publicos_count), str(privados_count), str(total_records), "100.0%", f"{tasa_res}% de Resolución Efectiva"])

            pdf_headers = []
            pdf_weights = []
            if include_req:
                pdf_headers.extend(["Código Solicitud", "Fecha Radicación", "Módulo Rector", "Tema Formativo Solicitado"])
                pdf_weights.extend([1.10, 0.95, 1.25, 2.20])
            pdf_headers.extend(["Plantel Educativo", "Código DEA", "Sector / Nivel", "Ubicación"])
            pdf_weights.extend([1.75, 0.80, 0.90, 0.95])
            if include_user:
                pdf_headers.append("Solicitante (Cédula / Cargo)")
                pdf_weights.append(1.35)
            if include_metrics:
                pdf_headers.extend(["Estatus Actual", "Atendida"])
                pdf_weights.extend([0.85, 0.65])

            # Si tiene más de 8 columnas usa Oficio (legal), si tiene 8 o menos usa Carta (letter)
            auto_page = 'legal' if len(pdf_headers) > 8 else 'letter'
            formato_txt = "Formato Oficio Horizontal" if auto_page == 'legal' else "Formato Carta Horizontal"

            report_meta = {
                'report_type': report_type, 'include_metrics': include_metrics, 'subtitle_scope': scope_label,
                'force_page_size': auto_page,
                'kpi_headers': ["TOTAL SOLICITUDES", "SOLICITUDES ATENDIDAS", "TASA DE RESOLUCIÓN", "IMPACTO POR SECTOR (SR-F-023)"],
                'kpi_values': [f"{total_records} Expedientes", f"{atendidas_count} Completadas", f"{tasa_res}%", f"Públicos: {publicos_count} | Privados: {privados_count}"],
                'summary_title': "1. Resumen Consolidado por Estatus Operativo y Sector Institucional",
                'summary_headers': ["Estatus de la Solicitud", "Sector Público", "Sector Privado", "Total Solicitudes", "% del Total", "Condición Operativa en el Corte"],
                'summary_rows': sum_rows,
                'summary_weights': [1.5, 0.9, 0.9, 0.9, 0.8, 2.5],
                'center_cols_summary': {"Sector Público", "Sector Privado", "Total Solicitudes", "% del Total"},
                'detail_title': f"2. Relación Detallada de Expedientes Registrados (Adaptado a {formato_txt})",
                'pdf_headers': pdf_headers,
                'pdf_rows': pdf_rows,
                'pdf_weights': pdf_weights,
                'center_cols_detail': {"Código Solicitud", "Fecha Radicación", "Código DEA", "Sector / Nivel", "Estatus Actual", "Atendida"}
            }

        return headers, data_rows, report_meta

    @staticmethod
    def get_scoped_base_query(user, filters):
        """
        [Parámetros heredados de US-56]
        Construye la consulta base de solicitudes blindada contra IDOR.
        Si el usuario es state_admin, sobrescribe obligatoriamente cualquier state_id recibido.
        """
        query = db.session.query(Request).select_from(Request)\
            .join(Request.institutional_staff)\
            .join(InstitutionalStaff.institution)\
            .join(Institution.parish)\
            .join(Parish.municipality)\
            .join(Municipality.state)

        user_role = user.roles_assoc[0].role.name if user.roles_assoc else 'applicant'

        # 1. Blindaje Territorial Forzoso
        if user_role == 'state_admin':
            state_info = get_user_state_info(user)
            authorized_state = state_info['state_id'] if state_info else 0
            query = query.filter(State.id == authorized_state)
        elif user_role == 'super_admin':
            requested_state = filters.get('state_id')
            if requested_state:
                query = query.filter(State.id == requested_state)
        else:
            return query.filter(Request.id == 0)

        # 2. Filtros Territoriales Dependientes
        if filters.get('municipality_id'):
            query = query.filter(Municipality.id == filters['municipality_id'])
        if filters.get('parish_id'):
            query = query.filter(Parish.id == filters['parish_id'])

        # 3. Filtros Temporales
        if filters.get('date_from'):
            query = query.filter(Request.created_at >= filters['date_from'])
        if filters.get('date_to'):
            query = query.filter(Request.created_at <= filters['date_to'])

        # 4. Clasificación Institucional (SR-F-023)
        if filters.get('institution_scope_id'):
            query = query.filter(Institution.institution_scope_id == filters['institution_scope_id'])
        if filters.get('institution_type_id'):
            query = query.filter(Institution.institution_type_id == filters['institution_type_id'])

        return query

    @staticmethod
    def get_indicators_timeline(user, filters):
        """
        Calcula las series temporales para las 3 tarjetas de líneas continuas:
        Generadas, Atendidas y Comparativa Consolidada.
        """
        base_q = AnalyticsService.get_scoped_base_query(user, filters)

        # Agrupación directa en PostgreSQL por día
        date_bucket = func.date_trunc('day', Request.created_at).label('hitorange')

        timeline_data = base_q.outerjoin(Request.plannings)\
            .join(Request.status)\
            .with_entities(
                date_bucket,
                func.count(Request.id).label('generadas'),
                func.count(
                    case((
                        and_(Status.status_code == 'STAT-007', RequestPlanning.attended == True),
                        Request.id
                    ))
                ).label('atendidas')
            )\
            .group_by('hitorange')\
            .order_by('hitorange').all()

        labels = [item.hitorange.strftime('%d %b') if item.hitorange else '' for item in timeline_data]
        generadas_series = [item.generadas for item in timeline_data]
        atendidas_series = [item.atendidas for item in timeline_data]

        total_gen = sum(generadas_series)
        total_atn = sum(atendidas_series)
        tasa_resolucion = round((total_atn / total_gen * 100), 1) if total_gen > 0 else 0.0

        return {
            'labels': labels,
            'generadas': generadas_series,
            'atendidas': atendidas_series,
            'summary': {
                'total_generadas': total_gen,
                'total_atendidas': total_atn,
                'tasa_resolucion': f"{tasa_resolucion}%"
            }
        }

    @staticmethod
    def get_indicators_initial_context(user):
        """
        Prepara los datos del mes en curso y catálogos protegidos para la Vista 2.
        """
        now = datetime.now(timezone.utc)
        user_role = user.roles_assoc[0].role.name if user.roles_assoc else 'applicant'
        state_info = get_user_state_info(user) if user_role == 'state_admin' else None

        # Catálogos geográficos respetando permisos
        if user_role == 'super_admin':
            states = State.query.order_by(State.name).all()
        else:
            states = [State.query.get(state_info['state_id'])] if state_info else []

        inst_types = InstitutionType.query.order_by(InstitutionType.name).all()
        inst_scopes = InstitutionScope.query.order_by(InstitutionScope.name).all()
        edu_levels = EducationalLevel.query.order_by(EducationalLevel.name).all()

        # Datos del mes corriente por defecto
        primer_dia_mes = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        filtros_iniciales = {
            'date_from': primer_dia_mes,
            'date_to': now,
            'state_id': state_info['state_id'] if state_info else None
        }
        timeline_data = AnalyticsService.get_indicators_timeline(user, filtros_iniciales)

        # Registro en Bitácora Institucional
        BinnacleService.create_log_entry(
            module=AuditModule.REQUESTS.value,
            action_type=AuditAction.CONSULTA_DETALLE.value,
            description=f"Acceso a consola de indicadores de gestión ({state_info['state_name'] if state_info else 'Nivel Nacional'})",
            status=AuditStatus.COMPLETADO.value
        )

        return {
            'user_role': user_role,
            'user_state': state_info,
            'states': states,
            'institution_types': inst_types,
            'institution_scopes': inst_scopes,
            'educational_levels': edu_levels,
            'initial_data': timeline_data
        }



