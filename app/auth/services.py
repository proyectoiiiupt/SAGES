from app.extensions import bcrypt
from app.models.user_model import User
from app.models.person_model import Person
from typing import Optional, Tuple


def authenticate_user(identifier: str, password: str) -> Tuple[bool, Optional[User], str]:

    person = Person.query.filter_by(identification_number=identifier).first()
    
    if person and person.user:
        user = person.user
    else:
        user = User.query.filter_by(user_name=identifier).first()

    if not user:
        return False, None, "Usuario y/o Contraseña inválidos."

    # Verificación directa exclusivamente con Flask-Bcrypt
    try:
        if not bcrypt.check_password_hash(user.password, password):
            return False, None, "Usuario y/o Contraseña inválidos."
    except Exception:
        return False, None, "Usuario y/o Contraseña inválidos."

    if not user.status or user.status.status_code != 'STAT-001':
        import logging
        logging.warning(f"Login denegado: user_id={user.id}, estado={getattr(user.status, 'status_name', 'SIN ESTADO')}")
        return False, None, "Usuario y/o Contraseña inválidos."

    return True, user, "Autenticación exitosa."