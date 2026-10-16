"""
Formularios WTForms del Módulo de Configuraciones Globales (SAGES)
Tarea: US-56-places-management
Proporciona validación de campos para el registro y edición de sedes operativas.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, Regexp


class PlaceForm(FlaskForm):
    """
    Formulario declarativo para el registro y edición de sedes físicas operativas.
    Valida nombre, jerarquía geográfica (Estado → Municipio → Parroquia),
    dirección física y teléfono en formato venezolano.
    """

    name = StringField(
        'Nombre de la Sede',
        validators=[
            DataRequired(message='El nombre de la sede es obligatorio.'),
            Length(min=3, max=200, message='El nombre debe tener entre 3 y 200 caracteres.')
        ]
    )

    state_id = SelectField(
        'Estado',
        choices=[],
        coerce=int,
        validators=[DataRequired(message='Debe seleccionar un Estado.')]
    )

    municipality_id = SelectField(
        'Municipio',
        choices=[(0, '— Seleccione Municipio —')],
        coerce=int,
        validators=[DataRequired(message='Debe seleccionar un Municipio.')]
    )

    parish_id = SelectField(
        'Parroquia',
        choices=[(0, '— Seleccione Parroquia —')],
        coerce=int,
        validators=[DataRequired(message='Debe seleccionar una Parroquia.')]
    )

    address = TextAreaField(
        'Dirección Física Detallada',
        validators=[
            DataRequired(message='La dirección es obligatoria.'),
            Length(min=10, max=500, message='La dirección debe tener entre 10 y 500 caracteres.')
        ]
    )

    phone = StringField(
        'Teléfono Directo',
        validators=[
            DataRequired(message='El teléfono es obligatorio.'),
            Regexp(
                r'^\(\d{4}\)-\d{7}$',
                message='Formato inválido. Use (XXXX)-XXXXXXX (ej: (0212)-1234567).'
            )
        ]
    )

    def __init__(self, *args, **kwargs):
        super(PlaceForm, self).__init__(*args, **kwargs)
        self._load_states()
        # municipality_id y parish_id se llenan dinámicamente vía JS/AJAX.
        # Los choices aquí son placeholder; la validación real de existencia
        # ocurre en el servicio al verificar el parish_id contra la BD.
        if not self.municipality_id.choices:
            self.municipality_id.choices = [(0, '— Seleccione Municipio —')]
        if not self.parish_id.choices:
            self.parish_id.choices = [(0, '— Seleccione Parroquia —')]

    def _load_states(self):
        """Carga todos los estados desde la BD para el selector de Estado."""
        from app.models.state_model import State
        states = State.query.order_by(State.name).all()
        self.state_id.choices = [(0, '— Seleccione Estado —')] + [
            (s.id, s.name) for s in states
        ]
