from datetime import date, timedelta
from flask_wtf import FlaskForm
from wtforms import DateField, TextAreaField, SelectField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

def coerce_optional_int(val):
    """
    Coerce flexible para SelectFields que pueden recibir valores nulos, vacíos o cadenas 'None'
    cuando se cargan dinámicamente desde el cliente.
    """
    if val is None or val == '' or str(val).strip() == '' or str(val).lower() == 'none':
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


class NewRequestWizardForm(FlaskForm):
    """
    Formulario con protección CSRF para el Wizard de Nueva Solicitud (US-34).
    Valida estrictamente los campos desde el backend.
    """
    training_id = SelectField(
        'Tema Formativo',
        validators=[DataRequired(message="Debe seleccionar un tema formativo válido.")],
        coerce=int
    )
    
    description = TextAreaField(
        'Justificación Institucional',
        validators=[
            DataRequired(message="La descripción es obligatoria."),
            Length(min=10, max=200, message="La justificación debe tener entre 10 y 200 caracteres.")
        ]
    )

class CancelRequestForm(FlaskForm):
    """
    Formulario simétrico para la cancelación motivada de solicitudes (US-44).
    Soporta validación tanto para el solicitante (mín. 10 caracteres) como
    para el administrador estadal / super administrador (mín. 20 caracteres).
    """
    reason_id = SelectField(
        'Motivo de Cancelación',
        validators=[DataRequired(message="Debe seleccionar un motivo válido del catálogo oficial.")],
        coerce=int
    )

    justification = TextAreaField(
        'Justificación Formal',
        validators=[
            DataRequired(message="La justificación explicativa es obligatoria."),
            Length(min=10, max=1000, message="La justificación debe tener entre 10 y 1000 caracteres.")
        ]
    )

    confirm_check = BooleanField(
        'Confirmación de Anulación',
        validators=[DataRequired(message="Debe marcar la casilla confirmando la anulación irreversible.")]
    )

    def __init__(self, min_length: int = 10, *args, **kwargs):
        super(CancelRequestForm, self).__init__(*args, **kwargs)
        self.min_length = min_length

    def validate_justification(self, field):
        text_val = (field.data or '').strip()
        if len(text_val) < self.min_length:
            raise ValidationError(
                f"La justificación debe contener al menos {self.min_length} caracteres válidos."
            )

# Alias de retrocompatibilidad para las vistas y rutas del solicitante
ApplicantCancelRequestForm = CancelRequestForm


class SatisfactionSurveyForm(FlaskForm):
    """
    Formulario de evaluación de calidad post-cierre (US-51 / SR-F-019).
    Tres criterios numéricos obligatorios (1–5 estrellas) y comentario opcional.
    Los valores son sincronizados desde inputs ocultos por requests_survey.js.
    """
    score_activity = IntegerField(
        '¿Qué le pareció la actividad formativa?',
        validators=[
            DataRequired(message="Debe calificar la actividad formativa."),
            NumberRange(min=1, max=5, message="La calificación debe estar entre 1 y 5 estrellas.")
        ]
    )
    score_instructor = IntegerField(
        '¿El facilitador explicó con claridad y resolvió dudas?',
        validators=[
            DataRequired(message="Debe calificar al facilitador."),
            NumberRange(min=1, max=5, message="La calificación debe estar entre 1 y 5 estrellas.")
        ]
    )
    score_admin_response = IntegerField(
        '¿Qué tan eficiente fue la respuesta de gestión?',
        validators=[
            DataRequired(message="Debe calificar la respuesta de gestión."),
            NumberRange(min=1, max=5, message="La calificación debe estar entre 1 y 5 estrellas.")
        ]
    )
    comment = TextAreaField(
        'Comentarios adicionales',
        validators=[
            Optional(),
            Length(max=1000, message="Los comentarios no pueden exceder 1000 caracteres.")
        ]
    )

class PlanTrainingForm(FlaskForm):
    """
    Formulario para planificar la fecha de la jornada (US-41).
    Valida SLA de 10 días, exigiendo justificación si se supera.
    """
    planned_for = DateField('Fecha Planificada', validators=[DataRequired(message="Debe seleccionar una fecha válida.")])
    notes = TextAreaField('Observaciones de Coordinación', validators=[Optional(), Length(max=500)])
    delay_reason_id = SelectField('Motivo de Retraso', coerce=coerce_optional_int, validate_choice=False, validators=[Optional()])
    delay_justification = TextAreaField('Justificación de Retraso', validators=[Optional(), Length(max=1000)])

    def __init__(self, execution_deadline=None, *args, **kwargs):
        super(PlanTrainingForm, self).__init__(*args, **kwargs)
        self.execution_deadline = execution_deadline

    def validate_planned_for(self, field):
        if not field.data:
            return

        if field.data <= date.today():
            raise ValidationError("La fecha debe ser estrictamente posterior al día de hoy.")
            
        if field.data.weekday() >= 5:  # 5 es Sábado, 6 es Domingo
            raise ValidationError("La fecha debe ser un día hábil (lunes a viernes).")
            
        max_allowed_date = date.today() + timedelta(days=30)
        if field.data > max_allowed_date:
            raise ValidationError(f"No puede planificar solicitudes más allá del {max_allowed_date.strftime('%d/%m/%Y')}.")

        deadline_date = self.execution_deadline.date() if hasattr(self.execution_deadline, 'date') else self.execution_deadline
        if deadline_date and field.data > deadline_date:
            # Validación Condicional de ANS
            if not self.delay_reason_id.data or str(self.delay_reason_id.data) == '0' or str(self.delay_reason_id.data) == 'None':
                raise ValidationError("La fecha supera el ANS de 10 días. Debe seleccionar un motivo de retraso.")
            if not self.delay_justification.data or len(self.delay_justification.data.strip()) < 20:
                raise ValidationError("La fecha supera el ANS de 10 días. Debe proporcionar una justificación válida (mín. 20 caracteres).")


class RescheduleRequestForm(FlaskForm):
    """
    Formulario para la reprogramación técnica de fecha por contingencia o causa mayor (US-42 / SR-F-022).
    Exige una nueva fecha estrictamente futura en día hábil, selección de motivo del catálogo oficial
    (sages.reasons) y una justificación técnica circunstanciada (mínimo 20 caracteres reales).
    """
    new_planned_for = DateField(
        'Nueva Fecha de Formación',
        validators=[DataRequired(message="Debe seleccionar una nueva fecha para la jornada.")]
    )
    reason_id = SelectField(
        'Motivo de la Reprogramación',
        coerce=coerce_optional_int,
        validators=[DataRequired(message="Debe seleccionar un motivo válido del catálogo oficial.")]
    )
    justification = TextAreaField(
        'Justificación Circunstanciada',
        validators=[
            DataRequired(message="La justificación técnica de la contingencia es obligatoria."),
            Length(min=20, max=1000, message="La justificación debe tener entre 20 y 1000 caracteres.")
        ]
    )

    def validate_new_planned_for(self, field):
        if not field.data:
            return
        if field.data <= date.today():
            raise ValidationError("La nueva fecha debe ser estrictamente posterior al día de hoy.")
        if field.data.weekday() >= 5:  # 5 es Sábado, 6 es Domingo
            raise ValidationError("La fecha debe ser un día hábil (lunes a viernes).")

    def validate_justification(self, field):
        text_val = (field.data or '').strip()
        if len(text_val) < 20:
            raise ValidationError("La justificación circunstanciada debe contener al menos 20 caracteres válidos.")

