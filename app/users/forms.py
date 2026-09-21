import re
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, PasswordField, IntegerField
from wtforms.validators import DataRequired, Length, Regexp, Optional, EqualTo, Email, ValidationError
from app.pre_registration.forms import validate_fk_exists

def safe_int_coerce(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

_PHONE_RE  = re.compile(r'^\+?[\d\s\-]{7,20}$')
_CEDULA_RE = re.compile(r'^[VEve]-\d{7,8}$')

def validate_venezuelan_phone(optional: bool = False):
    def _validator(form, field):
        value = (field.data or '').strip()
        if not value:
            if optional:
                return
            raise ValidationError(f'"{field.label.text}" es obligatorio.')
        if not _PHONE_RE.match(value):
            raise ValidationError(f'"{field.label.text}" tiene un formato inválido (Ej: (0414)-1234567).')
    return _validator

def validate_cedula_number():
    def _validator(form, field):
        number = (field.data or '').strip()
        if not number:
            raise ValidationError('El número de cédula es obligatorio.')
        id_type = 'V'
        if hasattr(form, 'identification_type') and form.identification_type.data:
            id_type = form.identification_type.data
        full = f'{id_type}-{number}'
        if not _CEDULA_RE.match(full):
            raise ValidationError('El número de cédula tiene un formato inválido (7-8 dígitos).')
    return _validator

class UserUpdateForm(FlaskForm):
    
    identification_number = StringField('Cédula', 
        filters=[lambda x: x.replace('.', '').strip() if x else x],
        validators=[
        DataRequired(message="La cédula es obligatoria."), 
        Length(min=7, max=8, message="Longitud de cédula inválida.")
    ])
    
    first_name = StringField('Primer Nombre', validators=[
        DataRequired(message="El primer nombre es obligatorio."), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message="Solo se permiten letras y espacios.")
    ])
    
    second_name = StringField('Segundo Nombre', validators=[
        Optional(), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message="Solo se permiten letras y espacios.")
    ])
    
    last_name = StringField('Primer Apellido', validators=[
        DataRequired(message="El primer apellido es obligatorio."), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message="Solo se permiten letras y espacios.")
    ])
    
    middle_name = StringField('Segundo Apellido', validators=[
        Optional(), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message="Solo se permiten letras y espacios.")
    ])
    
    
    position = SelectField('Cargo', coerce=int, validators=[
        DataRequired(message="El cargo es obligatorio.")
    ])


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Contraseña Actual', validators=[
        DataRequired(message="La contraseña actual es obligatoria.")
    ])
    
    new_password = PasswordField('Nueva Contraseña', validators=[
        DataRequired(message="La nueva contraseña es obligatoria."),
        Length(min=8, max=128, message="La contraseña debe tener entre 8 y 128 caracteres."),
        Regexp(
            r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[$@.!%*?&]).{8,128}$',
            message="La nueva contraseña debe tener al menos 8 caracteres, una mayúscula, un número y un carácter especial ($@.!%*?&)."
        )
    ])
    
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[
        DataRequired(message="Debe confirmar la nueva contraseña."),
        EqualTo('new_password', message="Las contraseñas no coinciden.")
    ])


class ProfileContactForm(FlaskForm):
    """
    Formulario para que el usuario edite sus datos de contacto:
    solo correo electrónico, teléfono principal y teléfono secundario.
    Los datos de identidad (cédula, nombres, rol) son de solo lectura.
    """
    email = StringField('Correo Electrónico', validators=[
        DataRequired(message="El correo electrónico es obligatorio."),
        Length(max=100, message="El correo no puede superar los 100 caracteres.")
    ])

    mobile = StringField('Teléfono Principal', 
        filters=[lambda x: re.sub(r'\D', '', x) if x else x],
        validators=[
        DataRequired(message="El teléfono principal es obligatorio."),
        Length(min=7, max=15, message="El teléfono principal debe tener entre 7 y 15 dígitos."),
        Regexp(r'^\d+$', message="El teléfono principal solo debe contener dígitos.")
    ])

    phone = StringField('Teléfono Secundario', 
        filters=[lambda x: re.sub(r'\D', '', x) if x else x],
        validators=[
        Optional(),
        Length(min=7, max=15, message="El teléfono secundario debe tener entre 7 y 15 dígitos."),
        Regexp(r'^\d*$', message="El teléfono secundario solo debe contener dígitos.")
    ])


class AdminUserRegisterForm(FlaskForm):
    """
    Formulario para el registro interno de personal administrativo (Super Admin / Admin Estadal).
    """
    role_id = SelectField('Rol', coerce=safe_int_coerce, validate_choice=False, validators=[
        DataRequired(message="El rol es obligatorio."),
        validate_fk_exists('Role')
    ])
    
    identification_type = SelectField('Tipo de Documento', choices=[('V', 'V'), ('E', 'E')], validators=[
        DataRequired(message="El tipo de documento es obligatorio.")
    ])
    
    identification_number = StringField('Cédula', 
        filters=[lambda x: re.sub(r'\D', '', x) if x else x],
        validators=[
        DataRequired(message="La cédula es obligatoria."), 
        Length(min=7, max=8, message="Longitud de cédula inválida."),
        validate_cedula_number()
    ])
    
    first_name = StringField('Primer Nombre', validators=[
        DataRequired(message="El primer nombre es obligatorio."), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message="Solo se permiten letras y espacios.")
    ])
    
    second_name = StringField('Segundo Nombre', validators=[
        Optional(), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message="Solo se permiten letras y espacios.")
    ])
    
    last_name = StringField('Primer Apellido', validators=[
        DataRequired(message="El primer apellido es obligatorio."), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message="Solo se permiten letras y espacios.")
    ])
    
    middle_name = StringField('Segundo Apellido', validators=[
        Optional(), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message="Solo se permiten letras y espacios.")
    ])
    
    email = StringField('Correo Electrónico', validators=[
        DataRequired(message="El correo electrónico es obligatorio."),
        Length(max=100, message="El correo no puede superar los 100 caracteres."),
        Email(message="El correo electrónico tiene un formato inválido.")
    ])

    mobile = StringField('Teléfono Principal', 
        filters=[lambda x: re.sub(r'\D', '', x) if x else x],
        validators=[
        DataRequired(message="El teléfono principal es obligatorio."),
        Length(max=20, message="El teléfono no puede exceder 20 caracteres."),
        validate_venezuelan_phone(optional=False)
    ])

    phone = StringField('Teléfono Secundario', 
        filters=[lambda x: re.sub(r'\D', '', x) if x else x],
        validators=[
        Optional(),
        Length(max=20, message="El teléfono no puede exceder 20 caracteres."),
        validate_venezuelan_phone(optional=True)
    ])
    
    state_id = SelectField('Estado', coerce=safe_int_coerce, validate_choice=False, validators=[
        DataRequired(message="El estado es obligatorio."),
        validate_fk_exists('State')
    ])
    
    place_id = SelectField('Sede', coerce=safe_int_coerce, validate_choice=False, validators=[
        DataRequired(message="La sede es obligatoria."),
        validate_fk_exists('Place')
    ])
    
    position_id = SelectField('Cargo', coerce=safe_int_coerce, validate_choice=False, validators=[
        DataRequired(message="El cargo es obligatorio."),
        validate_fk_exists('Position')
    ])