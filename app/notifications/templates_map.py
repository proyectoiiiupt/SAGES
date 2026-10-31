from app.notifications.enums import NotificationEvent, NotificationType

NOTIFICATION_TEMPLATES = {
    # =========================================================================
    # SOLICITUDES DE REGISTRO, PRE-REGISTRO Y CUENTAS (EXISTENTES - INTACTOS)
    # =========================================================================
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

    # =========================================================================
    # GESTIÓN DE INSTITUCIONES (EXISTENTES - INTACTOS)
    # =========================================================================
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
    },

    # =========================================================================
    # SOLICITUDES DE FORMACIÓN (3 EXISTENTES + 10 NUEVOS ACORDADOS)
    # =========================================================================
    NotificationEvent.REQUEST_CANCELLED_BY_APPLICANT: {
        "title": "Solicitud Cancelada por el Plantel: {institution_name}",
        "message_template": "El representante del plantel \"{institution_name}\" ha cancelado la solicitud de formación \"{training_name}\". Motivo: {reason_name}. Detalle: {justification}. El expediente ha sido archivado en el histórico institucional.",
        "default_type": NotificationType.WARNING,
        "required_context": ["institution_name", "training_name", "reason_name", "justification"]
    },
    NotificationEvent.REQUEST_CANCELLED_BY_ADMIN: {
        "title": "Solicitud Cancelada por CORPOELEC: {training_name}",
        "message_template": "La coordinación estadal ha cancelado la solicitud de formación \"{training_name}\" para el plantel \"{institution_name}\". Motivo: {reason_name}. Justificación: {justification}.",
        "default_type": NotificationType.DANGER,
        "required_context": ["institution_name", "training_name", "reason_name", "justification"]
    },
    NotificationEvent.REQUEST_RESCHEDULED: {
        "title": "Jornada Formativa Reprogramada: {training_name}",
        "message_template": "La coordinación de CORPOELEC ha reprogramado la jornada formativa \"{training_name}\" para el día {new_date}. Motivo oficial: {reason_name}. Explicación técnica: {justification}.",
        "default_type": NotificationType.WARNING,
        "required_context": ["institution_name", "training_name", "new_date", "reason_name", "justification"]
    },
    NotificationEvent.REQUEST_CREATED: {
        "title": "Nueva Solicitud de Formación ({request_code})",
        "message_template": "La institución '{institution_name}' ha registrado la solicitud {request_code} para el taller '{training_name}' ({participants} participantes). Requiere reclamo y atención en un plazo máximo de 48 horas.",
        "default_type": NotificationType.WARNING,
        "required_context": ["request_code", "institution_name", "training_name", "participants"]
    },
    NotificationEvent.REQUEST_CLAIMED: {
        "title": "Solicitud en Revisión ({request_code})",
        "message_template": "Su solicitud {request_code} para el taller '{training_name}' ha sido tomada en revisión por el coordinador estadal {admin_name}.",
        "default_type": NotificationType.INFO,
        "required_context": ["request_code", "training_name", "admin_name"]
    },
    NotificationEvent.REQUEST_PLANNED: {
        "title": "Jornada de Formación Planificada ({request_code})",
        "message_template": "¡Excelentes noticias! Su solicitud {request_code} ('{training_name}') ha sido agendada para el {planned_date} bajo modalidad '{modality}'. Ubicación/Enlace: {location_detail}.",
        "default_type": NotificationType.SUCCESS,
        "required_context": ["request_code", "training_name", "planned_date", "modality", "location_detail"]
    },
    NotificationEvent.REQUEST_COMPLETED: {
        "title": "Jornada Culminada Exitosamente ({request_code})",
        "message_template": "La jornada de formación de su solicitud {request_code} ('{training_name}') ha sido cerrada y certificada exitosamente por {admin_name}. ¡Gracias por su participación!",
        "default_type": NotificationType.SUCCESS,
        "required_context": ["request_code", "training_name", "admin_name"]
    },
    NotificationEvent.REQUEST_TRACKING_NOTE_ADDED: {
        "title": "Nueva Nota de Seguimiento en {request_code}",
        "message_template": "{author_name} ({author_role}) ha añadido una observación en la bitácora de la solicitud {request_code}: \"{note_preview}\"",
        "default_type": NotificationType.INFO,
        "required_context": ["author_name", "author_role", "request_code", "note_preview"]
    },
    NotificationEvent.REQUEST_SLA_DEMAND: {
        "title": "Reclamo de Atención por Retraso ({request_code})",
        "message_template": "La institución '{institution_name}' ha emitido un reclamo de atención sobre la solicitud {request_code} ({delay_stage}). Mensaje: \"{demand_message}\"",
        "default_type": NotificationType.DANGER,
        "required_context": ["institution_name", "request_code", "delay_stage", "demand_message"]
    },
    NotificationEvent.REQUEST_DELAY_JUSTIFIED: {
        "title": "Justificación de Retraso Registrada ({request_code})",
        "message_template": "El administrador {admin_name} ha registrado una justificación formal de retraso ({delay_stage}) en la solicitud {request_code} de '{institution_name}': \"{justification}\"",
        "default_type": NotificationType.INFO,
        "required_context": ["admin_name", "delay_stage", "request_code", "institution_name", "justification"]
    },
    NotificationEvent.REQUEST_DELAY_WARNING: {
        "title": "Alerta Preventiva de SLA 48h ({request_code})",
        "message_template": "La solicitud {request_code} de '{institution_name}' ha alcanzado las {hours_elapsed} horas en estado '{status_name}'. Atiéndala a la brevedad para evitar incumplimiento de SLA (>72h).",
        "default_type": NotificationType.WARNING,
        "required_context": ["request_code", "institution_name", "hours_elapsed", "status_name"]
    },
    NotificationEvent.REQUEST_DELAY_CRITICAL: {
        "title": "Incumplimiento Crítico de SLA ({request_code})",
        "message_template": "ALERTA DE AUDITORÍA: La solicitud {request_code} de '{institution_name}' presenta un retraso crítico ({delay_detail}) en estado '{status_name}'. Requiere atención y justificación obligatoria.",
        "default_type": NotificationType.DANGER,
        "required_context": ["request_code", "institution_name", "delay_detail", "status_name"]
    },
    NotificationEvent.REQUEST_PENDING_CLOSURE: {
        "title": "Cierre y Evidencias Pendientes ({request_code})",
        "message_template": "La fecha pautada ({planned_date}) para la solicitud {request_code} de '{institution_name}' ha concluido. Debe cargar el acta de asistencia y evidencias fotográficas para desbloquear su gestión.",
        "default_type": NotificationType.WARNING,
        "required_context": ["request_code", "institution_name", "planned_date"]
    },

    # =========================================================================
    # FORMACIÓN Y CATÁLOGO (app/trainings/)
    # =========================================================================
    NotificationEvent.TRAINING_MODULE_CREATED: {
        "title": "Nuevo Eje de Formación Disponible",
        "message_template": "Se ha incorporado el módulo formativo '{module_name}' al catálogo nacional por {admin_name}.",
        "default_type": NotificationType.SUCCESS,
        "required_context": ["module_name", "admin_name"]
    },
    NotificationEvent.TRAINING_MODULE_STATUS_CHANGED: {
        "title": "Cambio de Estado en Módulo Formativo",
        "message_template": "El módulo formativo '{module_name}' ha sido {action_label} en el catálogo nacional por {admin_name}.",
        "default_type": NotificationType.WARNING,
        "required_context": ["module_name", "action_label", "admin_name"]
    },
    NotificationEvent.TRAINING_TOPIC_CREATED: {
        "title": "Nuevo Taller Incorporado al Catálogo",
        "message_template": "Se ha habilitado el taller '{topic_name}' dentro del eje '{module_name}' por {admin_name}. Ya se encuentra disponible para planificación.",
        "default_type": NotificationType.INFO,
        "required_context": ["topic_name", "module_name", "admin_name"]
    },
    NotificationEvent.TRAINING_BULK_IMPORTED: {
        "title": "Actualización Masiva del Catálogo de Formación",
        "message_template": "{admin_name} ha completado una importación masiva del catálogo: {new_modules} módulos nuevos, {new_topics} talleres nuevos y {updated_topics} talleres actualizados.",
        "default_type": NotificationType.SUCCESS,
        "required_context": ["admin_name", "new_modules", "new_topics", "updated_topics"]
    },
    NotificationEvent.TRAINING_TOPIC_STATUS_CHANGED: {
        "title": "Cambio de Disponibilidad de Taller Formativo",
        "message_template": "El taller '{topic_name}' (Módulo: '{module_name}') ha sido {action_label} por {admin_name}.{impact_note}",
        "default_type": NotificationType.WARNING,
        "required_context": ["topic_name", "module_name", "action_label", "admin_name"]
    },
    NotificationEvent.TRAINING_TOPIC_DELETED: {
        "title": "Taller Retirado del Catálogo Nacional",
        "message_template": "El taller '{topic_name}' ha sido retirado definitivamente del catálogo por {admin_name}. Motivo: {reason}.",
        "default_type": NotificationType.DANGER,
        "required_context": ["topic_name", "admin_name", "reason"]
    },

    # =========================================================================
    # ESTADÍSTICAS Y AUDITORÍA (app/analytics/)
    # =========================================================================
    NotificationEvent.ANALYTICS_SECURITY_IDOR_ATTEMPT: {
        "title": "Alerta de Seguridad: Intento de Acceso No Autorizado",
        "message_template": "El usuario {actor_name} (ID: {actor_id}, Estado asignado: {actor_state}) intentó consultar o exportar métricas fuera de su jurisdicción (Estado solicitado: {target_state}) en '{endpoint_name}'. Acceso bloqueado.",
        "default_type": NotificationType.DANGER,
        "required_context": ["actor_name", "actor_id", "actor_state", "target_state", "endpoint_name"]
    },
    NotificationEvent.ANALYTICS_REPORT_EMAIL_STATUS: {
        "title": "Resultado de Envío de Reporte Estadístico",
        "message_template": "{status_message}",
        "default_type": NotificationType.SUCCESS,
        "required_context": ["status_message"]
    },

    # =========================================================================
    # CONFIGURACIONES Y PARÁMETROS (app/configurations/)
    # =========================================================================
    NotificationEvent.CONFIG_ROLE_PERMISSIONS_UPDATED: {
        "title": "Actualización de Permisos de Rol ('{role_name}')",
        "message_template": "{admin_name} ha modificado la matriz de accesos del rol '{role_name}' ({changes_summary}). Sus módulos habilitados se han actualizado automáticamente.",
        "default_type": NotificationType.WARNING,
        "required_context": ["role_name", "admin_name", "changes_summary"]
    },
    NotificationEvent.CONFIG_CORPORATE_UPDATED: {
        "title": "Actualización de Parámetros Institucionales",
        "message_template": "{admin_name} ha actualizado la configuración maestra de '{company_name}' ({updated_fields}). Los cambios ya se reflejan en reportes y comunicaciones oficiales.",
        "default_type": NotificationType.INFO,
        "required_context": ["admin_name", "company_name", "updated_fields"]
    },
    NotificationEvent.CONFIG_PLACE_CREATED: {
        "title": "Nueva Sede Operativa Registrada",
        "message_template": "{admin_name} ha registrado la sede '{place_name}' en el estado {state_name}. Ya está disponible para adscripción de personal y logística.",
        "default_type": NotificationType.SUCCESS,
        "required_context": ["admin_name", "place_name", "state_name"]
    },
    NotificationEvent.CONFIG_PLACE_UPDATED: {
        "title": "Actualización de Datos de su Sede Adscrita",
        "message_template": "Los datos maestros de su sede operativa ('{place_name}') han sido actualizados por {admin_name}.",
        "default_type": NotificationType.INFO,
        "required_context": ["place_name", "admin_name"]
    },
    NotificationEvent.CONFIG_PLACE_STATUS_CHANGED: {
        "title": "Cambio de Operatividad de Sede ('{place_name}')",
        "message_template": "La sede '{place_name}' (Estado {state_name}) ha sido {action_label} por {admin_name}.",
        "default_type": NotificationType.WARNING,
        "required_context": ["place_name", "state_name", "action_label", "admin_name"]
    },
    NotificationEvent.CONFIG_BACKUP_COMPLETED: {
        "title": "Respaldo de Base de Datos Generado",
        "message_template": "El administrador {admin_name} ha generado y descargado un respaldo completo del sistema ('{filename}').",
        "default_type": NotificationType.INFO,
        "required_context": ["admin_name", "filename"]
    }
}


class _SafeFormattingDict(dict):
    """Diccionario defensivo que retorna [key] si una clave no está presente, impidiendo KeyError."""
    def __missing__(self, key):
        return f"[{key}]"


def resolve_notification_payload(event: NotificationEvent, context: dict = None) -> dict:
    template = NOTIFICATION_TEMPLATES.get(event)
    if not template:
        raise ValueError(f"Evento de notificación no registrado: {event}")
    
    ctx = context.copy() if context else {}
    
    # Valores por defecto de contingencia para enriquecer el contexto si falta algún dato secundario
    defaults = {
        "state_name": "su jurisdicción",
        "dea_code": "S/C",
        "reason": "Actualización administrativa",
        "reason_name": "Causa operativa",
        "justification": "Sin justificación detallada",
        "user_name": "Usuario",
        "staff_name": "Colaborador",
        "institution_name": "Plantel Educativo",
        "request_code": "REQ-000",
        "training_name": "Actividad de Formación",
        "participants": "1",
        "admin_name": "Administración",
        "planned_date": "Por definir",
        "modality": "Presencial",
        "location_detail": "Instalaciones correspondientes",
        "author_name": "Usuario",
        "author_role": "Personal",
        "note_preview": "Nueva observación registrada",
        "delay_stage": "En proceso",
        "demand_message": "Solicitud de atención requerida",
        "hours_elapsed": "48",
        "status_name": "En Proceso",
        "delay_detail": "Demora acumulada",
        "module_name": "Módulo General",
        "topic_name": "Taller",
        "action_label": "actualizado",
        "impact_note": "",
        "new_modules": "0",
        "new_topics": "0",
        "updated_topics": "0",
        "actor_name": "Usuario",
        "actor_id": "0",
        "actor_state": "Nacional",
        "target_state": "Jurisdicción",
        "endpoint_name": "Módulo de Métricas",
        "status_message": "Operación completada",
        "role_name": "Rol",
        "changes_summary": "Permisos actualizados",
        "company_name": "CORPOELEC",
        "updated_fields": "Datos actualizados",
        "place_name": "Sede",
        "filename": "respaldo.sql"
    }
    for k, v in defaults.items():
        ctx.setdefault(k, v)

    # Formateo seguro contra KeyError
    safe_ctx = _SafeFormattingDict(ctx)
    message = template["message_template"].format_map(safe_ctx)
    title = template["title"].format_map(safe_ctx)
    
    return {
        "title": title,
        "message": message,
        "type": template["default_type"].value
    }
