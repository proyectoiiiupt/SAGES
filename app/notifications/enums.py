from enum import Enum

class NotificationType(str, Enum):
    INFO = "INFO"          # Azul corporativo SAGES: Avisos generales y auditoría
    SUCCESS = "SUCCESS"    # Verde institucional: Aprobaciones, altas exitosas y reactivaciones
    WARNING = "WARNING"    # Ámbar: Tareas pendientes de validación, cambio de credenciales
    DANGER = "DANGER"      # Rojo: Inactivación de planteles, rechazos, demoras críticas de respuesta

class NotificationEvent(str, Enum):
    # Solicitudes de Registro y Pre-Registro
    REGISTRATION_NEW_INSTITUTION = "REG_NEW_INST"      # Nueva institución pendiente por validar
    REGISTRATION_JOIN_INSTITUTION = "REG_JOIN_INST"    # Solicitud de afiliación a plantel existente
    REGISTRATION_INVITED_STAFF = "REG_INVITED_STAFF"   # Registro de colaborador invitado completado
    REGISTRATION_APPROVED = "REG_APPROVED"             # Aprobación de solicitud por admin estadal (hacia Super Admin)

    # Ciclo de Vida de Cuentas y Seguridad
    USER_WELCOME_FIRST_LOGIN = "USER_WELCOME"          # Bienvenida en primer inicio de sesión
    USER_PROFILE_UPDATED = "USER_PROFILE_UPDATED"      # Edición de ficha personal por rol superior

    # Gestión de Instituciones
    INSTITUTION_DATA_UPDATED = "INST_DATA_UPDATED"     # Edición de datos institucionales (notifica a afiliados)
    INSTITUTION_INACTIVATED = "INST_INACTIVATED"       # Plantel marcado como Inactivo (con motivo genérico)
    INSTITUTION_ACTIVATED = "INST_ACTIVATED"           # Plantel reactivado como Activo

    # Gestión de Solicitudes de Formación (3 existentes + 10 nuevos)
    REQUEST_CANCELLED_BY_APPLICANT = "REQ_CANCELLED_APPLICANT"  # Desistimiento voluntario del solicitante (US-44)
    REQUEST_CANCELLED_BY_ADMIN = "REQ_CANCELLED_ADMIN"          # Cancelación administrativa motivada por CORPOELEC (US-44)
    REQUEST_RESCHEDULED = "REQ_RESCHEDULED"                      # Reprogramación técnica de fecha por causa mayor (US-42)
    REQUEST_CREATED = "REQ_CREATED"                             # Nueva solicitud registrada por institución
    REQUEST_CLAIMED = "REQ_CLAIMED"                             # Solicitud tomada en revisión por coordinación
    REQUEST_PLANNED = "REQ_PLANNED"                             # Jornada formativa agendada
    REQUEST_COMPLETED = "REQ_COMPLETED"                         # Jornada cerrada y certificada
    REQUEST_TRACKING_NOTE_ADDED = "REQ_NOTE_ADDED"              # Nueva nota de bitácora
    REQUEST_SLA_DEMAND = "REQ_SLA_DEMAND"                       # Reclamo de atención por demora emitido por solicitante
    REQUEST_DELAY_JUSTIFIED = "REQ_DELAY_JUSTIFIED"             # Justificación formal de retraso registrada
    REQUEST_DELAY_WARNING = "REQ_DELAY_WARNING"                 # Alerta preventiva SLA 48h
    REQUEST_DELAY_CRITICAL = "REQ_DELAY_CRITICAL"               # Alerta crítica de retraso SLA (>72h o >10d)
    REQUEST_PENDING_CLOSURE = "REQ_PENDING_CLOSURE"             # Alerta de cierre y evidencias pendientes post-jornada

    # Módulo de Formación (Catálogo)
    TRAINING_MODULE_CREATED = "TRN_MOD_CREATED"                 # Nuevo eje temático creado
    TRAINING_MODULE_STATUS_CHANGED = "TRN_MOD_STATUS"           # Cambio de estado de módulo
    TRAINING_TOPIC_CREATED = "TRN_TOPIC_CREATED"                # Nuevo tema/taller registrado
    TRAINING_BULK_IMPORTED = "TRN_BULK_IMPORTED"                # Importación masiva de catálogo consolidada
    TRAINING_TOPIC_STATUS_CHANGED = "TRN_TOPIC_STATUS"          # Cambio de estado de tema/taller
    TRAINING_TOPIC_DELETED = "TRN_TOPIC_DELETED"                # Tema/taller retirado del catálogo

    # Módulo de Estadísticas
    ANALYTICS_SECURITY_IDOR_ATTEMPT = "ANL_IDOR_ALERT"          # Intento de acceso/exportación territorial no autorizado
    ANALYTICS_REPORT_EMAIL_STATUS = "ANL_REPORT_EMAIL"          # Resultado de envío asíncrono de reporte por correo

    # Módulo de Configuraciones
    CONFIG_ROLE_PERMISSIONS_UPDATED = "CFG_ROLE_PERMS"          # Actualización de matriz de permisos de rol
    CONFIG_CORPORATE_UPDATED = "CFG_CORP_UPDATED"               # Modificación de parámetros de la empresa
    CONFIG_PLACE_CREATED = "CFG_PLACE_CREATED"                  # Nueva sede operativa registrada
    CONFIG_PLACE_UPDATED = "CFG_PLACE_UPDATED"                  # Datos de sede operativa modificados
    CONFIG_PLACE_STATUS_CHANGED = "CFG_PLACE_STATUS"            # Cambio de operatividad de sede
    CONFIG_BACKUP_COMPLETED = "CFG_BACKUP_DONE"                 # Respaldo de sistema generado y descargado
