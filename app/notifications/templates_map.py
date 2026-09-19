from app.notifications.enums import NotificationEvent, NotificationType

NOTIFICATION_TEMPLATES = {
    NotificationEvent.REGISTRATION_NEW_INSTITUTION: {
        "title": "Nuevo Pre-Registro: {institution_name}",
        "message_template": "La institución educativa \"{institution_name}\" ha completado su pre-registro con comprobante adjunto. Pendiente por verificación administrativa.",
        "default_type": NotificationType.WARNING,
        "required_context": ["institution_name"]
    },
    NotificationEvent.REGISTRATION_JOIN_INSTITUTION: {
        "title": "Solicitud de Vinculación Institucional",
        "message_template": "El solicitante {user_name} ha solicitado vincularse al plantel \"{institution_name}\". Requiere revisión de recaudos en la bandeja de solicitudes.",
        "default_type": NotificationType.INFO,
        "required_context": ["user_name", "institution_name"]
    },
    NotificationEvent.REGISTRATION_INVITED_STAFF: {
        "title": "El colaborador invitado {staff_name} ha completado su registro exitosamente",
        "message_template": "El delegado institucional {staff_name} ha completado su registro exitosamente para la institución \"{institution_name}\". Requiere revisión de recaudos.",
        "default_type": NotificationType.SUCCESS,
        "required_context": ["staff_name", "institution_name"]
    },
    NotificationEvent.REGISTRATION_APPROVED: {
        "title": "Solicitud de registro aprobada",
        "message_template": "El Administrador Estadal de {state_name} {admin_name} ha aprobado las credenciales de {user_name} para el plantel \"{institution_name}\". Se ha despachado el enlace de activación.",
        "default_type": NotificationType.SUCCESS,
        "required_context": ["user_name", "institution_name", "state_name", "admin_name"]
    },
    NotificationEvent.USER_WELCOME_FIRST_LOGIN: {
        "title": "¡Bienvenido al Sistema {user_name}!",
        "message_template": "Tu cuenta de Usuario ha sido activada con éxito. Ya puedes comenzar a utilizar los módulos de la plataforma.",
        "default_type": NotificationType.INFO,
        "required_context": ["user_name"]
    },
    NotificationEvent.USER_PROFILE_UPDATED: {
        "title": "Actualización de Perfil",
        "message_template": "Los datos de tu perfil oficial han sido actualizados en el sistema por la administración central. Si no reconoces esta acción, contacta a soporte.",
        "default_type": NotificationType.INFO,
        "required_context": []
    },
    NotificationEvent.INSTITUTION_DATA_UPDATED: {
        "title": "Datos de Institución Modificados",
        "message_template": "La información oficial o de ubicación del plantel \"{institution_name}\" ha sido actualizada por la coordinación administrativa.",
        "default_type": NotificationType.INFO,
        "required_context": ["institution_name"]
    },
    NotificationEvent.INSTITUTION_INACTIVATED: {
        "title": "Atención: Institución Inactivada",
        "message_template": "El plantel \"{institution_name}\" ha pasado a estado Inactivo. La emisión de nuevas solicitudes de formación queda temporalmente suspendida.",
        "default_type": NotificationType.DANGER,
        "required_context": ["institution_name"]
    },
    NotificationEvent.INSTITUTION_ACTIVATED: {
        "title": "Institución Reactivada",
        "message_template": "El plantel \"{institution_name}\" ha sido reactivado operativamente. Los afiliados pueden gestionar y registrar solicitudes de formación con normalidad.",
        "default_type": NotificationType.SUCCESS,
        "required_context": ["institution_name"]
    }
}

def resolve_notification_payload(event: NotificationEvent, context: dict = None) -> dict:
    template = NOTIFICATION_TEMPLATES.get(event)
    if not template:
        raise ValueError(f"Evento de notificación no registrado: {event}")
    
    ctx = context.copy() if context else {}
    
    # Valores por defecto de contingencia para evitar excepciones si falta algún valor secundario
    defaults = {
        "state_name": "su jurisdicción",
        "dea_code": "S/C",
        "reason": "Actualización administrativa",
        "user_name": "Usuario",
        "staff_name": "Colaborador",
        "institution_name": "Plantel Educativo"
    }
    for k, v in defaults.items():
        ctx.setdefault(k, v)

    message = template["message_template"].format(**ctx)
    title = template["title"].format(**ctx)
    
    return {
        "title": title,
        "message": message,
        "type": template["default_type"].value
    }
