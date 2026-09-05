from werkzeug.security import check_password_hash as werkzeug_check
from app.extensions import bcrypt, db
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

    # Verificación con migración transparente:
    # 1. Intentar con bcrypt (contraseñas nuevas o ya migradas)
    # 2. Si falla, intentar con werkzeug (contraseñas antiguas) y migrar el hash automáticamente
    password_valid = False
    try:
        password_valid = bcrypt.check_password_hash(user.password, password)
    except Exception:
        pass

    if not password_valid:
        # Intentar con werkzeug (hash antiguo pbkdf2)
        try:
            if werkzeug_check(user.password, password):
                # Migración automática: re-hashear con bcrypt
                user.password = bcrypt.generate_password_hash(password).decode('utf-8')
                db.session.add(user)
                db.session.commit()
                password_valid = True
        except Exception:
            pass

    if not password_valid:
        return False, None, "Usuario y/o Contraseña inválidos."

    if not user.status or user.status.status_code != 'STAT-001':
        import logging
        logging.warning(f"Login denegado: user_id={user.id}, estado={getattr(user.status, 'status_name', 'SIN ESTADO')}")
        return False, None, "Usuario y/o Contraseña inválidos."

    return True, user, "Autenticación exitosa."