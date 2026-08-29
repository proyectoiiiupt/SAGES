from werkzeug.security import check_password_hash
from app.models.user_model import User
from app.models.person_model import Person
from app.models.status_model import Status
from typing import Optional, Tuple
from sqlalchemy.orm import joinedload

def authenticate_user(identifier: str, password: str) -> Tuple[bool, Optional[User], str]:

    person = Person.query.options(joinedload(Person.user).joinedload(User.status)).filter_by(identification_number=identifier).first()
    
    if person and person.user:
        user = person.user
    else:

        user = User.query.options(joinedload(User.status)).filter_by(user_name=identifier).first()

    if not user:
        return False, None, "Usuario y/o Contraseña inválidos."

    # Verificar si el usuario está activo
    if user.status.status_code != 'STAT-001':
        return False, None, "Su cuenta de usuario está inactiva. Contacte al administrador."

    if check_password_hash(user.password, password):
        # Verificar si el usuario está activo
        active_status = Status.query.filter_by(status_code='STAT-001').first()
        if user.status_id != active_status.id:
            return False, None, "Usuario inactivo. Contacte al administrador."

        return True, user, "Autenticación exitosa."
    
    return False, None, "Usuario y/o Contraseña inválidos."