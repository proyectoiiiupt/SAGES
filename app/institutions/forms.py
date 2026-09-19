"""
Formularios WTForms para el módulo de instituciones
Proporciona validación de seguridad y reglas de inserción de datos.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, Regexp, Optional


class InstitutionEditForm(FlaskForm):
    """
    Formulario WTForm para editar instituciones.
    Proporciona validación de seguridad y reglas de inserción de datos.
    """
    
    # Datos Generales (Administradores)
    plantel_code = StringField(
        'Código del Plantel (DEA)',
        validators=[
            Regexp(r'^[A-Z]{3}-[A-Z]{1}[0-9]{4}$', message='Formato inválido. Debe ser XXX-X0000 (ej: DEA-U0001)'),
            Length(min=9, max=9, message='El código debe tener 9 caracteres')
        ]
    )
    
    institution_name = StringField(
        'Nombre de la Institución',
        validators=[
            DataRequired(message='El nombre de la institución es requerido'),
            Length(min=3, max=200, message='El nombre debe tener entre 3 y 200 caracteres')
        ]
    )
    
    institution_type = SelectField(
        'Tipo de Institución',
        choices=[],
        validators=[DataRequired(message='Debe seleccionar un tipo de institución')]
    )
    
    institution_scope = SelectField(
        'Alcance de la Institución',
        choices=[],
        validators=[DataRequired(message='Debe seleccionar un alcance')]
    )
    
    institution_dependency = SelectField(
        'Dependencia',
        choices=[],
        validators=[DataRequired(message='Debe seleccionar una dependencia')]
    )
    
    # Ubicación (Administradores)
    state_id = SelectField(
        'Estado',
        choices=[],
        validators=[DataRequired(message='Debe seleccionar un estado')]
    )
    
    municipality_id = SelectField(
        'Municipio',
        choices=[],
        validators=[DataRequired(message='Debe seleccionar un municipio')]
    )
    
    parish_id = SelectField(
        'Parroquia',
        choices=[],
        validators=[DataRequired(message='Da seleccionar una parroquia')]
    )
    
    city_id = SelectField(
        'Ciudad',
        choices=[],
        validators=[DataRequired(message='Debe seleccionar una ciudad')]
    )
    
    # Datos de Contacto (Todos los usuarios)
    phone = StringField(
        'Teléfono Principal',
        validators=[
            DataRequired(message='El teléfono principal es requerido'),
            Length(min=11, max=14, message='El teléfono debe tener entre 11 y 14 caracteres')
        ]
    )
    
    address = TextAreaField(
        'Dirección Detallada',
        validators=[
            DataRequired(message='La dirección es requerida'),
            Length(min=10, max=500, message='La dirección debe tener entre 10 y 500 caracteres')
        ]
    )
    
    def __init__(self, *args, **kwargs):
        super(InstitutionEditForm, self).__init__(*args, **kwargs)
        
        # Cargar opciones dinámicamente
        self._load_institution_types()
        self._load_institution_scopes()
        self._load_institution_dependencies()
        self._load_states()
        self._load_municipalities()
        self._load_parishes()
        self._load_cities()
    
    def _load_institution_types(self):
        """Cargar tipos de institución desde la base de datos."""
        from app.models.institution_type_model import InstitutionType
        self.institution_type.choices = [(str(t.id), t.name) for t in InstitutionType.query.order_by(InstitutionType.name).all()]
    
    def _load_institution_scopes(self):
        """Cargar alcances de institución desde la base de datos."""
        from app.models.institution_scope_model import InstitutionScope
        self.institution_scope.choices = [(str(s.id), s.name) for s in InstitutionScope.query.order_by(InstitutionScope.name).all()]
    
    def _load_institution_dependencies(self):
        """Cargar dependencias de institución desde la base de datos."""
        from app.models.institution_dependency_model import InstitutionDependency
        self.institution_dependency.choices = [(str(d.id), d.name) for d in InstitutionDependency.query.order_by(InstitutionDependency.name).all()]
    
    def _load_states(self):
        """Cargar estados desde la base de datos."""
        from app.models.state_model import State
        self.state_id.choices = [(str(s.id), s.name) for s in State.query.order_by(State.name).all()]
    
    def _load_municipalities(self):
        """Cargar municipios desde la base de datos."""
        from app.models.municipality_model import Municipality
        self.municipality_id.choices = [(str(m.id), m.name) for m in Municipality.query.order_by(Municipality.name).all()]
    
    def _load_parishes(self):
        """Cargar parroquias desde la base de datos."""
        from app.models.parish_model import Parish
        self.parish_id.choices = [(str(p.id), p.name) for p in Parish.query.order_by(Parish.name).all()]
    
    def _load_cities(self):
        """Cargar ciudades desde la base de datos."""
        from app.models.city_model import City
        self.city_id.choices = [(str(c.id), c.name) for c in City.query.order_by(City.name).all()]


class InstitutionEditApplicantForm(FlaskForm):
    """
    Formulario WTForm simplificado para applicants.
    Solo permite editar teléfono y dirección.
    """
    
    phone = StringField(
        'Teléfono Principal',
        validators=[
            DataRequired(message='El teléfono principal es requerido'),
            Regexp(r'^\(\d{4}\)-\d{7}$', message='Formato inválido. Debe ser (XXXX)-XXXXXXX (ej: (0414)-1234567)'),
            Length(min=14, max=14, message='El teléfono debe tener 14 caracteres')
        ]
    )
    
    address = TextAreaField(
        'Dirección Detallada',
        validators=[
            DataRequired(message='La dirección es requerida'),
            Length(min=10, max=500, message='La dirección debe tener entre 10 y 500 caracteres')
        ]
    )
