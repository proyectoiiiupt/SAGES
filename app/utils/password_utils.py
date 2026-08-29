from werkzeug.security import generate_password_hash
from app.extensions import db

def change_user_password(user, new_password):
    """
    Actualiza la contraseña del usuario de forma segura.
    Genera el hash de la nueva contraseña y guarda los cambios en la base de datos.
    """
    user.password = generate_password_hash(new_password)
    db.session.add(user)
    db.session.commit()
    return True
