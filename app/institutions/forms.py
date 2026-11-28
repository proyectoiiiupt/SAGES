"""
Formularios WTForms para el módulo de instituciones
Proporciona formularios separados y validación de seguridad por rol:
- InstitutionApplicantEditForm: teléfono y dirección para applicants (plantel activo).
- InstitutionStateAdminEditForm: datos generales, clasificación MPPE (incluyendo niveles educativos),
  y ubicación (municipio y parroquia) restringida a su estado asignado (state_id y plantel_code bloqueados).
- InstitutionSuperAdminEditForm: edición completa, permitiendo modificar state_id y desbloquear plantel_code.
"""
import re
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SelectMultipleField
from wtforms.validators import DataRequired, Length, Regexp, Optional, ValidationError

_PHONE_RE = re.compile(r'^\+?[\d\s\-]{7,20}$')


def validate_venezuelan_phone(optional: bool = True):
    """Valida formato de número telefónico nacional o internacional."""
    def _validator(form, field):
        value = (field.data or '').strip()
        if not value:
            if optional:
                return
            raise ValidationError(f'"{field.label.text}" es obligatorio.')
        if not _PHONE_RE.match(value):
            raise ValidationError(
                f'"{field.label.text}" tiene un formato inválido (Ej: 0414-1234567 o +58 212 1234567).'
            )
    return _validator


class InstitutionApplicantEditForm(FlaskForm):
    """
    Formulario WTForm para el rol applicant.
    Permite editar únicamente teléfono institucional y dirección detallada.
    """
    phone = StringField(
        'Teléfono Institucional',
        validators=[
            Optional(),
            Length(max=20, message='El teléfono no puede exceder 20 caracteres'),
            validate_venezuelan_phone(optional=True)
        ]
    )

    address = TextAreaField(
        'Dirección Detallada',
        validators=[
            DataRequired(message='La dirección es requerida'),
            Length(min=10, max=500, message='La dirección debe tener entre 10 y 500 caracteres')
        ]
    )


class InstitutionStateAdminEditForm(FlaskForm):
    """
    Formulario WTForm para el rol state_admin.
    Permite editar teléfono, dirección, nombre, clasificación MPPE (tipo, alcance, dependencia,
    niveles educativos) y ubicación (municipio y parroquia de su estado asignado).
    state_id y plantel_code permanecen bloqueados. Ciudad es inmutable.
    """
    phone = StringField(
        'Teléfono Institucional',
        validators=[
            Optional(),
            Length(max=20, message='El teléfono no puede exceder 20 caracteres'),
            validate_venezuelan_phone(optional=True)
        ]
    )

    address = TextAreaField(
        'Dirección Detallada',
        validators=[
            DataRequired(message='La dirección es requerida'),
            Length(min=10, max=500, message='La dirección debe tener entre 10 y 500 caracteres')
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

    educational_levels = SelectMultipleField(
        'Niveles Educativos',
        choices=[],
        coerce=str,
        validators=[Optional()]
    )

    municipality_id = SelectField(
        'Municipio',
        choices=[],
        validators=[DataRequired(message='Debe seleccionar un municipio')]
    )

    parish_id = SelectField(
        'Parroquia',
        choices=[],
        validators=[DataRequired(message='Debe seleccionar una parroquia')]
    )

    def __init__(self, *args, state_id=None, **kwargs):
        super(InstitutionStateAdminEditForm, self).__init__(*args, **kwargs)
        self._load_institution_types()
        self._load_institution_scopes()
        self._load_institution_dependencies()
        self._load_educational_levels()
        self._load_municipalities(state_id=state_id)
        self._load_parishes(state_id=state_id)

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

    def _load_educational_levels(self):
        """Cargar todos los niveles educativos disponibles."""
        from app.models.educational_level_model import EducationalLevel
        self.educational_levels.choices = [(str(lvl.id), lvl.name) for lvl in EducationalLevel.query.order_by(EducationalLevel.id).all()]

    def _load_municipalities(self, state_id=None):
        """Cargar municipios, opcionalmente filtrados por el estado del state_admin."""
        from app.models.municipality_model import Municipality
        query = Municipality.query
        if state_id:
            query = query.filter_by(state_id=state_id)
        self.municipality_id.choices = [(str(m.id), m.name) for m in query.order_by(Municipality.name).all()]

    def _load_parishes(self, state_id=None):
        """Cargar parroquias, opcionalmente filtradas por el estado del state_admin."""
        from app.models.parish_model import Parish
        from app.models.municipality_model import Municipality
        query = Parish.query
        if state_id:
            query = query.join(Municipality).filter(Municipality.state_id == state_id)
        self.parish_id.choices = [(str(p.id), p.name) for p in query.order_by(Parish.name).all()]


class InstitutionSuperAdminEditForm(InstitutionStateAdminEditForm):
    """
    Formulario WTForm para el rol super_admin.
    Permite modificar todos los campos, incluyendo state_id y desbloqueo de plantel_code.
    """
    state_id = SelectField(
        'Estado',
        choices=[],
        validators=[DataRequired(message='Debe seleccionar un estado')]
    )

    plantel_code = StringField(
        'Código del Plantel (DEA)',
        validators=[
            DataRequired(message='El código del plantel es requerido'),
            Regexp(r'^[A-Z0-9\-]{4,20}$', message='Formato inválido. Debe contener entre 4 y 20 caracteres (mayúsculas, números y guiones)'),
            Length(min=4, max=20, message='El código debe tener entre 4 y 20 caracteres')
        ]
    )

    def __init__(self, *args, **kwargs):
        # super_admin no restringe municipios ni parroquias a un estado específico
        kwargs.pop('state_id', None)
        super(InstitutionSuperAdminEditForm, self).__init__(*args, state_id=None, **kwargs)
        self._load_states()

    def _load_states(self):
        """Cargar estados desde la base de datos."""
        from app.models.state_model import State
        self.state_id.choices = [(str(s.id), s.name) for s in State.query.order_by(State.name).all()]


# Alias para retrocompatibilidad
InstitutionEditApplicantForm = InstitutionApplicantEditForm
InstitutionEditForm = InstitutionSuperAdminEditForm
