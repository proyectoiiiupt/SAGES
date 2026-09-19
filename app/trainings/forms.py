"""
Formularios para el Módulo de Formación (Trainings)
Maneja la validación de entrada para módulos y temas formativos.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length, ValidationError
from app.models.training_module_model import TrainingModule


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
