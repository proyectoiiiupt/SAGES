from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField
from wtforms.validators import DataRequired, Length

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


