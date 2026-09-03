"""Generación y validación de tokens para invitaciones de colaboradores."""

from datetime import timedelta
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask import current_app

INVITATION_MAX_AGE = 48 * 60 * 60


def _serializer():
    # El SECRET_KEY garantiza que solo la aplicación pueda firmar tokens válidos.
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='institution-invitation')


def create_invitation_token(institution_id, position_id, email, identification_number):
    # El token firmado transporta la invitación sin persistirla en la base de datos.
    return _serializer().dumps({
        'institution_id': institution_id,
        'position_id': position_id,
        'email': email,
        'identification_number': identification_number
    })


def read_invitation_token(token):
    # La firma y la antigüedad validan que el enlace no haya sido alterado ni vencido.
    try:
        return _serializer().loads(token, max_age=INVITATION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def invitation_expiration():
    # Mantiene disponible el cálculo de vencimiento para cualquier flujo futuro.
    from datetime import datetime, timezone
    return datetime.now(timezone.utc) + timedelta(seconds=INVITATION_MAX_AGE)
