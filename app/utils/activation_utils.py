from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

def generate_activation_token(payload: dict) -> str:
    """
    Serializa y firma criptográficamente los datos con la SECRET_KEY de Flask.
    Salting específico: 'sages-account-activation'.
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='sages-account-activation')
    return serializer.dumps(payload)

def verify_activation_token(token: str, max_age_seconds: int = 172800) -> dict | None:
    """
    Verifica la integridad de la firma y la vigencia temporal (48 horas por defecto).
    Retorna el diccionario de datos o None si expiró o fue alterado.
    """
    status, payload = inspect_activation_token(token, max_age_seconds)
    return payload if status == 'valid' else None


def inspect_activation_token(token: str, max_age_seconds: int = 172800) -> tuple[str, dict | None]:
    """
    Inspecciona el token distinguiendo entre:
    - ('valid', payload): Válido y dentro de las 48 horas.
    - ('expired', payload): Token auténtico pero fuera del plazo de 48 horas.
    - ('invalid', None): Token alterado o firma no válida.
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='sages-account-activation')
    try:
        return 'valid', serializer.loads(token, max_age=max_age_seconds)
    except SignatureExpired as e:
        try:
            return 'expired', serializer.load_payload(e.payload)
        except Exception:
            return 'invalid', None
    except BadSignature:
        return 'invalid', None