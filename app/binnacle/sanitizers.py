import uuid
from datetime import datetime, date
from decimal import Decimal

# Lista de claves consideradas sensibles que no deben persistirse nunca en base de datos.
SENSITIVE_KEYS = {
    'password', 
    'password_hash', 
    'token', 
    'csrf_token', 
    'secret_key', 
    'captcha_token', 
    'code', 
    'session_id',
    'current_password',
    'new_password'
}

REDACTED_PLACEHOLDER = "[PROTEGIDO]"

def sanitize_payload(data: dict) -> dict:
    """
    Recorre recursivamente un diccionario y ofusca cualquier clave 
    que se encuentre en SENSITIVE_KEYS. Además, convierte objetos no 
    serializables por JSON (como datetime o uuid) a cadenas.
    """
    if not isinstance(data, dict):
        return data

    sanitized = {}
    for k, v in data.items():
        if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
            sanitized[k] = REDACTED_PLACEHOLDER
        elif isinstance(v, dict):
            sanitized[k] = sanitize_payload(v)
        elif isinstance(v, list):
            sanitized[k] = [sanitize_payload(item) if isinstance(item, dict) else sanitize_value(item) for item in v]
        else:
            sanitized[k] = sanitize_value(v)

    return sanitized

def sanitize_value(val):
    """Convierte objetos que no son serializables a JSON estándar a un formato string seguro."""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    elif isinstance(val, uuid.UUID):
        return str(val)
    elif isinstance(val, Decimal):
        return float(val)  # O str(val) según la necesidad
    return val