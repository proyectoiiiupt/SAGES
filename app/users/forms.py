from flask_wtf import FlaskForm
from wtforms import StringField, SelectField
from wtforms.validators import DataRequired, Length, Regexp, Optional

class UserUpdateForm(FlaskForm):
    
    identification_number = StringField('Cédula', validators=[
        DataRequired(message="La cédula es obligatoria."), 
        Length(min=7, max=10, message="Longitud de cédula inválida.")
    ])
    
    first_name = StringField('Primer Nombre', validators=[
        DataRequired(message="El primer nombre es obligatorio."), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ]+$', message="Solo se permiten letras, sin espacios.")
    ])
    
    second_name = StringField('Segundo Nombre', validators=[
        Optional(), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ]+$', message="Solo se permiten letras, sin espacios.")
    ])
    
    last_name = StringField('Primer Apellido', validators=[
        DataRequired(message="El primer apellido es obligatorio."), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ]+$', message="Solo se permiten letras, sin espacios.")
    ])
    
    middle_name = StringField('Segundo Apellido', validators=[
        Optional(), 
        Regexp(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ]+$', message="Solo se permiten letras, sin espacios.")
    ])
    
    
    position = SelectField('Cargo', coerce=int, validators=[
        DataRequired(message="El cargo es obligatorio.")
    ])