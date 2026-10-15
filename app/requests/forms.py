from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

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

class ApplicantCancelRequestForm(FlaskForm):
    """
    Formulario para el desistimiento voluntario justificado del solicitante (US-44).
    Exige la selección de un motivo de catálogo y justificación de al menos 10 caracteres.
    """
    reason_id = SelectField(
        'Motivo de Desistimiento',
        validators=[DataRequired(message="Debe seleccionar un motivo válido del catálogo.")],
        coerce=int
    )
    
    justification = TextAreaField(
        'Justificación Formal',
        validators=[
            DataRequired(message="La justificación del desistimiento es obligatoria."),
            Length(min=10, max=500, message="La justificación debe tener entre 10 y 500 caracteres.")
        ]
    )


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
