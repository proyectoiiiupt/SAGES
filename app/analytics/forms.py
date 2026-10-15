from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, RadioField
from wtforms.validators import DataRequired, Length


class ReportWizardForm(FlaskForm):
    """
    Formulario para el Asistente de Reportes Parametrizados en 2 Pasos.
    """
    # ── PASO 1: PARÁMETROS DEL REPORTE ──
    report_name = StringField(
        'Nombre del Reporte',
        validators=[
            DataRequired(message="Debe asignar un nombre al reporte."),
            Length(min=3, max=150, message="El nombre debe tener entre 3 y 150 caracteres.")
        ]
    )

    report_type = SelectField(
        'Tipo de Reporte',
        choices=[
            ('gestion_general', 'Rendimiento y Actividad de Gestión'),
            ('impacto_educativo', 'Impacto Social y Cobertura Educativa (SR-F-023)'),
            ('retrasos_ans', 'Analítico de Justificaciones y Retrasos ANS (SR-F-026)'),
            ('auditoria_usuarios', 'Actividad de Usuario y Auditoría')
        ],
        validators=[DataRequired(message="Debe seleccionar el tipo de reporte.")]
    )

    include_user_data = BooleanField('Incluir datos de Usuario / Solicitante', default=True)
    include_request_details = BooleanField('Incluir detalles de Solicitudes', default=True)
    include_metrics = BooleanField('Incluir Métricas y Totales', default=True)

    # ── PASO 2: OPCIONES DE EXPORTACIÓN ──
    export_format = RadioField(
        'Formato de Archivo',
        choices=[
            ('pdf', 'PDF (.pdf)'),
            ('xlsx', 'Excel (.xlsx)'),
            ('csv', 'CSV (.csv)')
        ],
        default='pdf',
        validators=[DataRequired(message="Seleccione un formato de exportación.")]
    )

    delivery_method = RadioField(
        'Método de Entrega',
        choices=[
            ('local', 'Guardar en este Equipo (Descarga directa)'),
            ('email', 'Enviar por Correo Electrónico')
        ],
        default='local',
        validators=[DataRequired(message="Seleccione el método de entrega.")]
    )
