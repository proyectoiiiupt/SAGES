from app.extensions import db, bcrypt

def check_user_password(pw_hash: str, password: str) -> bool:
    """
    Verifica una contraseña contra su hash usando exclusivamente Flask-Bcrypt.
    Si el hash no coincide o es inválido, retorna False.
    """
    if not pw_hash or not password:
        return False
    try:
        return bcrypt.check_password_hash(pw_hash, password)
    except Exception:
        return False

def hash_password(password: str) -> str:
    """
    Genera el hash seguro de una contraseña usando Flask-Bcrypt y lo decodifica a string UTF-8.
    """
    return bcrypt.generate_password_hash(password).decode('utf-8')

def change_user_password(user, new_password: str) -> bool:
    """
    Actualiza la contraseña del usuario de forma segura usando Flask-Bcrypt.
    Genera el hash bcrypt de la nueva contraseña, lo decodifica a UTF-8 y guarda los cambios en la base de datos.
    """
    user.password = hash_password(new_password)
    db.session.add(user)
    db.session.commit()
    return True
