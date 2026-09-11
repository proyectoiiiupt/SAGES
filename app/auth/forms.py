from flask_wtf import FlaskForm
from wtforms import PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo

class ActivationPasswordForm(FlaskForm):
    password = PasswordField('Nueva Contraseña', validators=[
        DataRequired(message="La contraseña es obligatoria."),
        Length(min=8, message="La contraseña debe tener al menos 8 caracteres.")
    ])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[
        DataRequired(message="Debe confirmar la contraseña."),
        EqualTo('password', message="Las contraseñas no coinciden.")
    ])
    submit = SubmitField('Activar Cuenta')