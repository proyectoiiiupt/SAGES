from datetime import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, RadioField, IntegerField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, Regexp, ValidationError
from werkzeug.datastructures import MultiDict


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


class IndicatorsFilterForm(FlaskForm):
    """
    Validador de parámetros de filtrado para la consola de indicadores (Vista 2).
    Soporta consumo tanto desde JSON (payload) como desde Form data.
    Sanitiza cadenas vacías ('') a None para prevenir fallos en campos enteros y de fecha.
    """
    class Meta:
        # Se desactiva la validación CSRF interna del Form para validarla
        # a nivel de cabecera HTTP X-CSRFToken con CSRFProtect global
        csrf = False

    time_mode = StringField(
        'Modo de Tiempo',
        default='month',
        filters=[lambda v: (v.strip() if isinstance(v, str) and v.strip() else 'month')],
        validators=[
            Optional(),
            Regexp(r'^(month|range)$', message="Modo temporal inválido (debe ser 'month' o 'range').")
        ]
    )
    month = IntegerField(
        'Mes',
        validators=[
            Optional(),
            NumberRange(min=1, max=12, message="Mes inválido (debe estar comprendido entre 1 y 12).")
        ]
    )
    date_from = StringField(
        'Fecha Desde',
        filters=[lambda v: (v.strip() if isinstance(v, str) else v), lambda v: (None if v == '' else v)],
        validators=[
            Optional(),
            Regexp(r'^\d{4}-\d{2}-\d{2}$', message="Formato de fecha inválido en Fecha Desde (YYYY-MM-DD).")
        ]
    )
    date_to = StringField(
        'Fecha Hasta',
        filters=[lambda v: (v.strip() if isinstance(v, str) else v), lambda v: (None if v == '' else v)],
        validators=[
            Optional(),
            Regexp(r'^\d{4}-\d{2}-\d{2}$', message="Formato de fecha inválido en Fecha Hasta (YYYY-MM-DD).")
        ]
    )
    state_id = IntegerField('Estado', validators=[Optional()])
    municipality_id = IntegerField('Municipio', validators=[Optional()])
    parish_id = IntegerField('Parroquia', validators=[Optional()])
    institution_scope_id = IntegerField('Sector', validators=[Optional()])
    educational_level_id = IntegerField('Nivel Educativo', validators=[Optional()])

    def __init__(self, formdata=None, *args, **kwargs):
        """
        Constructor adaptable: si recibe un diccionario de datos (vía data= o como primer argumento),
        lo convierte defensivamente a MultiDict sanitizando strings vacíos a '' para que WTForms
        no dispare errores de conversión espurios sobre campos opcionales.
        """
        data = kwargs.get('data')
        if formdata is not None and isinstance(formdata, dict) and not isinstance(formdata, MultiDict):
            data = formdata
            formdata = None

        if data is not None and isinstance(data, dict):
            form_dict = MultiDict()
            for k, v in data.items():
                if v is not None and str(v).strip() != '':
                    form_dict.add(k, str(v).strip())
                else:
                    form_dict.add(k, '')
            formdata = form_dict
            kwargs.pop('data', None)

        super().__init__(formdata=formdata, *args, **kwargs)

    @classmethod
    def from_json(cls, json_data):
        """
        Instancia de conveniencia para procesar payloads JSON limpios.
        """
        return cls(data=json_data)

    def validate_date_from(self, field):
        """
        Verifica que la fecha 'Desde' corresponda a una fecha de calendario real (ej. rechaza 2026-02-31).
        """
        if field.data:
            try:
                datetime.strptime(field.data, '%Y-%m-%d')
            except ValueError:
                raise ValidationError("Fecha Desde no corresponde a una fecha válida en el calendario.")

    def validate_date_to(self, field):
        """
        Verifica que la fecha 'Hasta' sea válida en el calendario y no sea anterior a 'Desde'.
        """
        if field.data:
            try:
                d_to = datetime.strptime(field.data, '%Y-%m-%d').date()
            except ValueError:
                raise ValidationError("Fecha Hasta no corresponde a una fecha válida en el calendario.")

            if self.date_from.data:
                try:
                    d_from = datetime.strptime(self.date_from.data, '%Y-%m-%d').date()
                except ValueError:
                    d_from = None

                if d_from and d_from > d_to:
                    raise ValidationError("La fecha 'Desde' no puede ser posterior a la fecha 'Hasta'.")

    def get_clean_filters(self):
        """
        Retorna los parámetros sanitizados y tipados listos para ser consumidos
        por AnalyticsService.calculate_filtered_indicators().
        """
        def _empty_to_none(val):
            if val is None or (isinstance(val, str) and not val.strip()):
                return None
            return val

        return {
            'time_mode': self.time_mode.data or 'month',
            'month': self.month.data,
            'date_from': _empty_to_none(self.date_from.data),
            'date_to': _empty_to_none(self.date_to.data),
            'state_id': self.state_id.data,
            'municipality_id': self.municipality_id.data,
            'parish_id': self.parish_id.data,
            'institution_scope_id': self.institution_scope_id.data,
            'educational_level_id': self.educational_level_id.data
        }
