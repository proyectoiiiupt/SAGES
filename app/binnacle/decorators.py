import functools
from typing import Optional
from flask import request
from app.binnacle.services import BinnacleService
from app.binnacle.types import AuditStatus

def audit_activity(
    module: str, 
    action_type: str, 
    description: str, 
    status: str = AuditStatus.COMPLETADO.value
):
    """
    Decorador declarativo para interceptar endpoints y registrar su ejecución
    en la bitácora automáticamente si la petición es exitosa.
    Ideal para acciones que no mutan la base de datos (ej. Descarga de reportes).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Ejecutar la función original
            response = func(*args, **kwargs)

            # Registrar solo si la respuesta es exitosa (código 2xx o 3xx)
            # En Flask, response puede ser una tupla, string, o un objeto Response
            status_code = 200
            if hasattr(response, 'status_code'):
                status_code = response.status_code
            elif isinstance(response, tuple) and len(response) >= 2 and isinstance(response[1], int):
                status_code = response[1]

            if status_code < 400:
                BinnacleService.create_log_entry(
                    module=module,
                    action_type=action_type,
                    description=description,
                    status=status
                )
            return response
        return wrapper
    return decorator