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
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='sages-account-activation')
    try:
        return serializer.loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None