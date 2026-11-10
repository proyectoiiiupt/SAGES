import os
import diskcache

# Directorio de caché persistente para el control de sesiones activas concurrentes
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.cache', 'sessions')
_session_cache = diskcache.Cache(CACHE_DIR)

def set_active_session(user_id: int, token: str, expire_seconds: int = 604800) -> None:
    """
    Registra el token de la sesión activa única para un usuario.
    Por defecto tiene una expiración de 7 días (604800 segundos), que se renueva
    en cada inicio de sesión exitoso.
    """
    key = f"user_active_session_{int(user_id)}"
    _session_cache.set(key, token, expire=expire_seconds)

def get_active_session(user_id: int) -> str | None:
    """
    Obtiene el token de la sesión activa actual del usuario en el servidor.
    Retorna None si no hay sesión activa registrada o si ya expiró.
    """
    key = f"user_active_session_{int(user_id)}"
    return _session_cache.get(key)

def clear_active_session(user_id: int, token: str | None = None) -> None:
    """
    Elimina la sesión activa del usuario.
    Si se proporciona un token, solo se elimina si coincide con la sesión activa actual en el servidor,
    evitando que una sesión previa o desactualizada elimine la sesión activa de otro dispositivo.
    Si token es None, realiza un borrado administrativo forzado de la sesión.
    """
    key = f"user_active_session_{int(user_id)}"
    if token is not None:
        current_token = _session_cache.get(key)
        if current_token and current_token != token:
            return
    _session_cache.delete(key)

