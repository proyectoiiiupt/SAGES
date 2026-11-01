"""
Formularios para el Módulo de Formación (Trainings)
Maneja la validación de entrada para módulos y temas formativos.
"""
from flask_wtf import FlaskForm
from app.models.training_module_model import TrainingModule
from wtforms import StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, ValidationError, Optional
from app.users.forms import safe_int_coerce
from app.pre_registration.forms import validate_fk_exists
from app.models.training_model import Training

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

class ModuleEditForm(FlaskForm):
    """
    Formulario exclusivo para la edición de Módulo Rector.
    Permite actualizar nombre y descripción operativa.
    """
    def __init__(self, *args, module_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.module_id = module_id

    name = StringField(
        'Nombre del Módulo Rector',
        filters=[lambda x: x.strip() if x else x],
        validators=[
            DataRequired(message="El nombre del módulo rector es obligatorio."),
            Length(min=3, max=200, message="El nombre debe tener entre 3 y 200 caracteres.")
        ]
    )

    description = TextAreaField(
        'Descripción Operativa',
        filters=[lambda x: x.strip() if x else x],
        validators=[
            DataRequired(message="La descripción operativa es obligatoria."),
            Length(min=10, max=2000, message="La descripción debe tener entre 10 y 2000 caracteres.")
        ]
    )

    def validate_name(self, field):
        """Valida que no exista otro módulo con el mismo nombre (ignora mayúsculas/minúsculas)."""
        if not field.data:
            return
        query = TrainingModule.query.filter(
            TrainingModule.name.ilike(field.data.strip())
        )
        if self.module_id:
            query = query.filter(TrainingModule.id != self.module_id)
        if query.first():
            raise ValidationError("Ya existe otro módulo rector registrado con este nombre.")

class TrainingForm(FlaskForm):
    """
    Formulario para el registro de un nuevo Tema Formativo.
    """
    training_module_id = SelectField(
        'Módulo Rector',
        coerce=safe_int_coerce,
        validate_choice=False,
        validators=[
            DataRequired(message='Debe seleccionar el Módulo Rector de adscripción.'),
            validate_fk_exists('TrainingModule')
        ]
    )

    name = StringField(
        'Título del Tema Formativo',
        validators=[
            DataRequired(message='El título del tema formativo es obligatorio.'),
            Length(min=5, max=200, message='El título debe tener entre 5 y 200 caracteres.')
        ]
    )

    description = TextAreaField(
        'Descripción Programática',
        validators=[
            DataRequired(message='La descripción programática es obligatoria.'),
            Length(min=15, max=1000, message='La descripción debe tener entre 15 y 1000 caracteres.')
        ]
    )

    def validate_name(self, field):
        """Valida que no exista otro tema con el mismo título en el mismo módulo."""
        if not field.data or not self.training_module_id.data:
            return
            
        exists = Training.query.filter(
            Training.name.ilike(field.data.strip()),
            Training.training_module_id == self.training_module_id.data,
            Training.deleted_at.is_(None)
        ).first()
        
        if exists:
            raise ValidationError("Ya existe un tema formativo registrado con este título en el módulo seleccionado.")


class TrainingEditForm(FlaskForm):
    """
    Formulario exclusivo para la edición de Tema Formativo.
    """
    def __init__(self, *args, training_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.training_id = training_id

    training_module_id = SelectField(
        'Módulo Rector',
        coerce=safe_int_coerce,
        validate_choice=False,
        validators=[
            DataRequired(message='Debe seleccionar el Módulo Rector de adscripción.'),
            validate_fk_exists('TrainingModule')
        ]
    )

    name = StringField(
        'Título del Tema Formativo',
        filters=[lambda x: x.strip() if x else x],
        validators=[
            DataRequired(message='El título del tema formativo es obligatorio.'),
            Length(min=5, max=200, message='El título debe tener entre 5 y 200 caracteres.')
        ]
    )

    description = TextAreaField(
        'Descripción Programática',
        filters=[lambda x: x.strip() if x else x],
        validators=[
            DataRequired(message='La descripción programática es obligatoria.'),
            Length(min=15, max=1000, message='La descripción debe tener entre 15 y 1000 caracteres.')
        ]
    )

    def validate_name(self, field):
        """Valida que no exista otro tema con el mismo título (excluyendo el actual)."""
        if not field.data or not self.training_module_id.data:
            return
            
        query = Training.query.filter(
            Training.name.ilike(field.data.strip()),
            Training.training_module_id == self.training_module_id.data,
            Training.deleted_at.is_(None)
        )
        
        # Excluimos el ID actual de la búsqueda de duplicados
        if self.training_id:
            query = query.filter(Training.id != self.training_id)
            
        if query.first():
            raise ValidationError("Ya existe otro tema formativo registrado con este título en el módulo seleccionado.")