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
