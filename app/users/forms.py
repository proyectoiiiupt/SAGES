from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, PasswordField
from wtforms.validators import DataRequired, Length, Regexp, Optional, EqualTo

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

    mobile = StringField('Teléfono Principal', validators=[
        DataRequired(message="El teléfono principal es obligatorio."),
        Length(min=7, max=15, message="El teléfono principal debe tener entre 7 y 15 dígitos."),
        Regexp(r'^\d+$', message="El teléfono principal solo debe contener dígitos.")
    ])

    phone = StringField('Teléfono Secundario', validators=[
        Optional(),
        Length(min=7, max=15, message="El teléfono secundario debe tener entre 7 y 15 dígitos."),
        Regexp(r'^\d*$', message="El teléfono secundario solo debe contener dígitos.")
    ])