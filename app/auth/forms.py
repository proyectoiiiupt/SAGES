from flask_wtf import FlaskForm
from wtforms import PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, Regexp

class ActivationPasswordForm(FlaskForm):
    password = PasswordField('Nueva Contraseña', validators=[
        DataRequired(message="La contraseña es obligatoria."),
        Length(min=8, max=128, message="La contraseña debe tener entre 8 y 128 caracteres."),
        Regexp(r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[$@.!%*?&]).{8,128}$', message="La contraseña no cumple con los criterios de seguridad.")
    ])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[
        DataRequired(message="Debe confirmar la contraseña."),
        EqualTo('password', message="Las contraseñas no coinciden.")
    ])
    submit = SubmitField('Activar Cuenta')