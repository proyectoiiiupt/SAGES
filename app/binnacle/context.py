from flask import request, has_request_context
from flask_login import current_user

def get_audit_context() -> dict:
    """
    Extrae el contexto de auditoría (IP, User Agent, ID del usuario actual, etc.)
    de forma segura, validando si existe un contexto de Request activo.
    Esto permite que la auditoría funcione incluso en tareas en segundo plano
    (CLI, scripts, celery, etc).
    """
    context = {
        'ip_address': '127.0.0.1',
        'user_agent': 'SYSTEM_WORKER',
        'user_id': None,
        'session_id': None
    }

    if has_request_context():
        # Intentar obtener la IP real detrás de proxies si está disponible
        # fallback al remote_addr estándar
        if request.headers.getlist("X-Forwarded-For"):
            context['ip_address'] = request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
        elif request.remote_addr:
            context['ip_address'] = request.remote_addr

        if request.user_agent:
            context['user_agent'] = request.user_agent.string

        # Extraer el usuario logueado si Flask-Login está configurado y el usuario autenticado
        if current_user and current_user.is_authenticated:
            context['user_id'] = current_user.id

    return context