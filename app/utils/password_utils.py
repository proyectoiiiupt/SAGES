import secrets
from flask import has_request_context, session
from flask_login import current_user
from app.extensions import db, bcrypt
from app.auth.session_store import set_active_session

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
    Actualiza la contraseña del usuario de forma segura usando Flask-Bcrypt
    y rota el token de sesión activa para invalidar inmediatamente cualquier
    sesión previa abierta en otros dispositivos o navegadores.
    """
    user.password = hash_password(new_password)
    db.session.add(user)
    db.session.commit()

    # Rotar el token de sesión activa única en el servidor (diskcache)
    new_token = secrets.token_hex(32)
    set_active_session(user.id, new_token)

    # Si la acción proviene del usuario actualmente autenticado en su perfil,
    # sincronizar su sesión local para mantener su dispositivo actual activo.
    if has_request_context():
        if getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'id', None) == user.id:
            session['session_token'] = new_token

    return True
