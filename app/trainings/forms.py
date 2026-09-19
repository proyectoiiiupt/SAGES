"""
Formularios WTForms para el módulo de Formación (Trainings).
Proporciona validación de seguridad y reglas de captura para Módulos Rectores.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class TrainingModuleForm(FlaskForm):
    """
    Formulario para el registro de un nuevo Módulo Rector.
    
    Regla de negocio:
      - 'module_code' es un identificador técnico de base de datos autogenerado en backend (MOD-XXX),
        invisible para usuarios finales y no asignable manualmente. Se define como solo lectura.
      - 'name', 'description' y 'order_index' son los campos capturados para el usuario.
    """
    module_code = StringField(
        'Código del Módulo',
        render_kw={
            'readonly': True,
            'placeholder': 'Autogenerado por el sistema (ej. MOD-005)',
            'class': 'readonly-field'
        },
        validators=[Optional()]
    )

    name = StringField(
        'Nombre del Módulo Rector',
        validators=[
            DataRequired(message='El nombre del módulo rector es obligatorio.'),
            Length(min=3, max=200, message='El nombre debe tener entre 3 y 200 caracteres.')
        ]
    )

    description = TextAreaField(
        'Descripción',
        validators=[
            DataRequired(message='La descripción es obligatoria.'),
            Length(min=10, max=1000, message='La descripción debe tener entre 10 y 1000 caracteres.')
        ]
    )
