import os
from datetime import datetime, timedelta
import diskcache

# Usamos un directorio de caché persistente dentro de la carpeta del proyecto
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.cache', 'tokens')
_cache = diskcache.Cache(CACHE_DIR)

def set_token(email: str, code: str, minutes: int = 5):
    key = email.lower()
    entry = {
        'code': code,
        'expires_at': datetime.utcnow() + timedelta(minutes=minutes),
        'attempts': 0
    }
    # Guardamos en caché y le decimos a diskcache que expire automáticamente
    _cache.set(key, entry, expire=minutes * 60)

def validate_token_attempt(email: str, code: str, max_attempts: int = 3) -> str:
    """Check token validity, increment attempts if incorrect. Consumes the token if valid."""
    key = email.lower()
    
    from diskcache import Lock
    lock = Lock(_cache, f"lock:{key}", expire=30)
    
    with lock:
        entry = _cache.get(key)
        
        if not entry:
            return 'EXPIRED'
        
        if datetime.utcnow() > entry['expires_at']:
            _cache.delete(key)
            return 'EXPIRED'

        if entry.get('attempts', 0) >= max_attempts:
            _cache.delete(key)
            return 'BLOCKED'

        if entry['code'] != code:
            entry['attempts'] = entry.get('attempts', 0) + 1
            if entry['attempts'] >= max_attempts:
                _cache.delete(key)
                return 'BLOCKED'
            
            # Actualizamos el contador de intentos en la caché
            # Calculamos cuánto tiempo le queda para mantener la misma expiración
            remaining = (entry['expires_at'] - datetime.utcnow()).total_seconds()
            if remaining > 0:
                _cache.set(key, entry, expire=remaining)
            return 'INVALID'

        # Si es válido, CONSUMIMOS el token atómicamente para prevenir doble uso
        _cache.delete(key)
        return 'VALID'

def get_remaining_seconds(email: str) -> int:
    key = email.lower()
    entry = _cache.get(key)
    if not entry:
        return 0
    remaining = entry['expires_at'] - datetime.utcnow()
    return max(0, int(remaining.total_seconds()))

def invalidate_token(email: str):
    """Destruye el token activo inmediatamente para prevenir abusos."""
    key = email.lower()
    _cache.delete(key)