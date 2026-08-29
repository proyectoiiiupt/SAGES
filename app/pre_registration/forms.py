"""
pre_registration/forms.py
--------------------------
Definición declarativa de formularios con WTForms/Flask-WTF para el
flujo de pre-registro público.

Este módulo concentra todas las reglas de validación (longitud, expresiones 
regulares, obligatoriedad) para los campos ingresados por el usuario,
separando la capa de validación de la capa de rutas.
"""

import re
import importlib
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, IntegerField
from wtforms.validators import (
    DataRequired, Optional, Length, Email, Regexp, ValidationError
)

# Constantes de longitud máxima para los campos
MAX_STR_LEN       = 200
MAX_TEXT_LEN      = 500
MAX_EMAIL_LEN     = 100
MAX_PHONE_LEN     = 20
MAX_ID_NUMBER_LEN = 20
MAX_CODE_LEN      = 50

_PHONE_RE  = re.compile(r'^\+?[\d\s\-]{7,20}$')
_CEDULA_RE = re.compile(r'^[VEve]-\d{7,8}$')


def validate_venezuelan_phone(optional: bool = False):
    """
    Valida el formato de un número telefónico venezolano o internacional.

    Args:
        optional (bool): Si es True, permite que el campo esté vacío sin lanzar error.

    Returns:
        Callable: Función de validación para WTForms.
        
    Raises:
        ValidationError: Si el formato del teléfono es incorrecto o si está vacío siendo obligatorio.
    """
    def _validator(form, field):
        value = (field.data or '').strip()
        if not value:
            if optional:
                return
            raise ValidationError(f'"{field.label.text}" es obligatorio.')
        if not _PHONE_RE.match(value):
            raise ValidationError(
                f'"{field.label.text}" tiene un formato inválido '
                '(Ej: (0414)-1234567).'
            )
    return _validator


def validate_cedula_number():
    """
    Valida el número de cédula venezolana reconstruyéndola con su prefijo (V/E).

    Returns:
        Callable: Función de validación para WTForms.

    Raises:
        ValidationError: Si el campo está vacío o el formato reconstruido no coincide con el patrón.
    """
    def _validator(form, field):
        number = (field.data or '').strip()
        if not number:
            raise ValidationError('El número de cédula es obligatorio.')
        id_type = 'V'
        if hasattr(form, 'identification_type') and form.identification_type.data:
            id_type = form.identification_type.data
        full = f'{id_type}-{number}'
        if not _CEDULA_RE.match(full):
            raise ValidationError(
                'El número de cédula tiene un formato inválido (7-8 dígitos).'
            )
    return _validator


def validate_fk_exists(model_name: str, field_name: str = 'id'):
    """
    Comprueba si el valor ingresado existe como llave foránea (Foreign Key) en la BD.

    Args:
        model_name (str): Nombre del modelo SQLAlchemy a consultar.
        field_name (str): Nombre de la columna en el modelo (por defecto 'id').

    Returns:
        Callable: Función de validación para WTForms.

    Raises:
        ValidationError: Si el valor no existe en la tabla o el modelo no es válido.
    """
    def _validator(form, field):
        value = field.data
        if not value:
            return
            
        from flask import g
        from app.extensions import db
        from sqlalchemy import select
        
        cache_key = f'fk_{model_name}_{field_name}_{value}'
        if hasattr(g, cache_key):
            if not getattr(g, cache_key):
                raise ValidationError(f'El valor seleccionado para "{field.label.text}" no es válido o no existe en el sistema.')
            return
        
        try:
            models = importlib.import_module('app.models')
            model_class = getattr(models, model_name)
        except (ImportError, AttributeError):
            raise ValidationError('Error de validación: La opción seleccionada no es válida.')
            
        exists = db.session.execute(
            select(model_class).filter(getattr(model_class, field_name) == value)
        ).scalar() is not None
        
        setattr(g, cache_key, exists)
        if not exists:
            raise ValidationError(f'El valor seleccionado para "{field.label.text}" no es válido o no existe en el sistema.')
            
    return _validator


class PlantelCodeForm(FlaskForm):
    """
    Formulario para validar la estructura del código de plantel institucional.
    
    Verifica que el código cumpla con los requisitos alfanuméricos antes de 
    consultar su disponibilidad en la base de datos.
    """
    plantel_code = StringField(
        'Código de Plantel',
        validators=[
            DataRequired(message='El código de plantel es obligatorio.'),
            Length(
                min=3, max=MAX_CODE_LEN,
                message='El código debe tener entre %(min)d y %(max)d caracteres.'
            ),
            Regexp(
                r'^[A-Za-z0-9\-_]{3,50}$',
                message='Solo se permiten letras, números, guiones y '
                        'guiones bajos (mín. 3 caracteres).'
            ),
        ]
    )

    class Meta:
        csrf = False


class EmailCheckForm(FlaskForm):
    """
    Formulario para validar el formato de un correo electrónico.
    """
    email = StringField(
        'Correo Electrónico',
        validators=[
            DataRequired(message='El correo electrónico es obligatorio.'),
            Length(max=MAX_EMAIL_LEN,
                   message='El correo no puede exceder %(max)d caracteres.'),
            Email(message='El correo electrónico tiene un formato inválido.'),
        ]
    )

    class Meta:
        csrf = False


class CedulaCheckForm(FlaskForm):
    """
    Formulario para validar preliminarmente la longitud del número de cédula.
    """
    identification_number = StringField(
        'Número de Cédula',
        validators=[
            DataRequired(message='La cédula es obligatoria.'),
            Length(min=7, max=8, message='La cédula debe tener entre 7 y 8 caracteres.')
        ]
    )

    class Meta:
        csrf = False


class InstitutionForm(FlaskForm):
    """
    Formulario integral para validar los datos de la institución educativa.
    
    Se utiliza en el paso final del pre-registro para asegurar que todos los datos
    institucionales y sus respectivas llaves foráneas sean correctos.
    """
    plantel_code = StringField(
        'Código de Plantel',
        validators=[
            DataRequired(message='El código de plantel es obligatorio.'),
            Length(min=3, max=MAX_CODE_LEN,
                   message='El código debe tener entre %(min)d y %(max)d caracteres.'),
            Regexp(
                r'^[A-Za-z0-9\-_]{3,50}$',
                message='Código de plantel con formato inválido.'
            ),
        ]
    )

    institution_name = StringField(
        'Nombre o Razón Social',
        validators=[
            DataRequired(message='El nombre de la institución es obligatorio.'),
            Length(min=3, max=MAX_STR_LEN,
                   message='El nombre debe tener al menos %(min)d caracteres.'),
        ]
    )

    institution_prefix = StringField(
        'Prefijo',
        validators=[
            Optional(),
            Length(max=50, message='El prefijo no puede exceder %(max)d caracteres.'),
        ]
    )

    institution_acronym = StringField(
        'Acrónimo / Siglas',
        validators=[
            Optional(),
            Length(max=20, message='Las siglas no pueden exceder %(max)d caracteres.'),
            Regexp(
                r'^[A-Za-z0-9Ññ]{1,20}$',
                message='Las siglas solo deben contener letras y números (sin espacios ni puntos).'
            ),
        ]
    )

    institution_type_id = StringField(
        'Tipo de Institución',
        validators=[
            DataRequired(message='Seleccione el tipo de institución.'),
            Regexp(
                r'^INST-\d{3}$',
                message='Código de tipo de institución inválido.'
            ),
            validate_fk_exists('InstitutionType', 'institution_type_code')
        ]
    )

    institution_scope_id = IntegerField(
        'Sector',
        validators=[
            DataRequired(message='Seleccione el sector de la institución.'),
            validate_fk_exists('InstitutionScope')
        ]
    )

    institution_dependency_id = IntegerField(
        'Dependencia',
        validators=[
            DataRequired(message='Seleccione la dependencia institucional.'),
            validate_fk_exists('InstitutionDependency')
        ]
    )

    phone = StringField(
        'Teléfono Institucional',
        validators=[
            Optional(),
            Length(max=MAX_PHONE_LEN,
                   message='El teléfono no puede exceder %(max)d caracteres.'),
            validate_venezuelan_phone(optional=True),
        ]
    )

    parish_id = IntegerField(
        'Parroquia',
        validators=[
            DataRequired(message='Seleccione la parroquia.'),
            validate_fk_exists('Parish')
        ]
    )

    address = TextAreaField(
        'Dirección de la Sede',
        validators=[
            DataRequired(message='La dirección de la sede es obligatoria.'),
            Length(
                min=10, max=MAX_TEXT_LEN,
                message='La dirección debe ser más descriptiva '
                        '(mín. %(min)d caracteres).'
            ),
        ]
    )

    class Meta:
        csrf = False


class PersonForm(FlaskForm):
    """
    Formulario integral para validar los datos personales del representante institucional.
    
    Gestiona validaciones cruzadas como el tipo y número de identificación,
    y asegura el formato correcto de los datos de contacto.
    """
    identification_type = SelectField(
        'Tipo de Cédula',
        choices=[('V', 'Venezolano (V)'), ('E', 'Extranjero (E)')],
        validators=[DataRequired(message='El tipo de cédula debe ser V o E.')]
    )

    identification_number = StringField(
        'Número de Cédula',
        validators=[
            DataRequired(message='El número de cédula es obligatorio.'),
            Length(max=MAX_ID_NUMBER_LEN,
                   message='El número de cédula es demasiado largo.'),
            validate_cedula_number(),
        ]
    )

    first_name = StringField(
        'Primer Nombre',
        validators=[
            DataRequired(message='El primer nombre es obligatorio.'),
            Length(min=2, max=MAX_STR_LEN,
                   message='"Primer Nombre" debe tener al menos %(min)d caracteres.'),
        ]
    )

    second_name = StringField(
        'Segundo Nombre',
        validators=[
            Optional(),
            Length(min=2, max=MAX_STR_LEN,
                   message='"Segundo Nombre" debe tener al menos %(min)d caracteres.'),
        ]
    )

    last_name = StringField(
        'Primer Apellido',
        validators=[
            DataRequired(message='El primer apellido es obligatorio.'),
            Length(min=2, max=MAX_STR_LEN,
                   message='"Primer Apellido" debe tener al menos %(min)d caracteres.'),
        ]
    )

    middle_name = StringField(
        'Segundo Apellido',
        validators=[
            Optional(),
            Length(min=2, max=MAX_STR_LEN,
                   message='"Segundo Apellido" debe tener al menos %(min)d caracteres.'),
        ]
    )

    email = StringField(
        'Correo Electrónico',
        validators=[
            DataRequired(message='El correo electrónico es obligatorio.'),
            Length(max=MAX_EMAIL_LEN,
                   message='El correo no puede exceder %(max)d caracteres.'),
            Email(message='El correo electrónico tiene un formato inválido.'),
        ]
    )

    mobile = StringField(
        'Teléfono Principal',
        validators=[
            DataRequired(message='El teléfono principal es obligatorio.'),
            Length(max=MAX_PHONE_LEN,
                   message='El teléfono no puede exceder %(max)d caracteres.'),
            validate_venezuelan_phone(optional=False),
        ]
    )

    phone = StringField(
        'Teléfono Secundario',
        validators=[
            Optional(),
            Length(max=MAX_PHONE_LEN,
                   message='El teléfono no puede exceder %(max)d caracteres.'),
            validate_venezuelan_phone(optional=True),
        ]
    )

    position_id = IntegerField(
        'Cargo',
        validators=[
            DataRequired(message='Seleccione su cargo.'),
            validate_fk_exists('Position')
        ]
    )

    class Meta:
        csrf = False


def collect_errors(form: FlaskForm) -> list[str]:
    """
    Convierte el diccionario de errores de un formulario WTForms en una lista plana de strings.

    Args:
        form (FlaskForm): La instancia del formulario que falló la validación.

    Returns:
        list[str]: Lista con todos los mensajes de error encontrados.
    """
    errors: list[str] = []
    for field_errors in form.errors.values():
        errors.extend(field_errors)
    return errors