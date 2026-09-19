import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.extensions import db
from app.models.binnacle_model import Binnacle
from app.binnacle.types import AuditStatus, AuditModule, AuditAction
from app.binnacle.context import get_audit_context

logger = logging.getLogger(__name__)

class BinnacleService:
    """
    Servicio centralizado para la creación de registros de bitácora.
    Maneja tanto la inserción síncrona dentro de la transacción actual, 
    como la inserción en transacciones aisladas para fallos de seguridad.
    """

    @classmethod
    def log_security_event(
        cls, 
        action_type: str, 
        description: str, 
        module: str = AuditModule.AUTH.value,
        status: str = AuditStatus.COMPLETADO.value,
        user=None,
        user_identifier: Optional[str] = None
    ) -> None:
        """
        Registra un evento de seguridad de forma aislada.
        Crea su propia conexión a base de datos y ejecuta un commit independiente,
        para evitar que si el Request principal falla y hace rollback, se pierda el log.
        """
        context = get_audit_context()

        # Si pasan el objeto de usuario, usamos su id
        user_id = user.id if user else context.get('user_id')

        # En caso de no haber ID, intentamos extraer user_identifier explícito

        try:
            # Crear una nueva sesión temporal específicamente para este log
            # Así nos independizamos de la sesión principal (db.session)
            engine = db.engine
            with Session(engine) as session:
                log = Binnacle(
                    module=module,
                    action_type=action_type,
                    description=description,
                    status=status,
                    user_id=user_id,
                    user_identifier=user_identifier,
                    ip_address=context['ip_address'],
                    user_agent=context['user_agent'],
                    session_id=context['session_id']
                )
                session.add(log)
                session.commit()
        except Exception as e:
            logger.error(f"Fallo crítico al escribir en la bitácora de seguridad: {str(e)}")

    @classmethod
    def create_log_entry(
        cls,
        module: str,
        action_type: str,
        description: str,
        status: str = AuditStatus.COMPLETADO.value,
        target_table: Optional[str] = None,
        record_id: Optional[int] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        user_identifier: Optional[str] = None,
        session_instance: Optional[Session] = None
    ) -> Optional[Binnacle]:
        """
        Crea un registro de auditoría asociado a la sesión activa (por defecto db.session).
        Si ocurre dentro de un flush_hook, se debe pasar la 'session_instance' para 
        evitar recursión o problemas de estado en SQLAlchemy.
        """
        context = get_audit_context()

        log = Binnacle(
            module=module,
            action_type=action_type,
            description=description,
            status=status,
            target_table=target_table,
            record_id=record_id,
            old_values=old_values,
            new_values=new_values,
            user_id=context['user_id'],
            user_identifier=user_identifier,
            ip_address=context['ip_address'],
            user_agent=context['user_agent'],
            session_id=context['session_id']
        )

        # Si nos proveen una sesión explícita (ej. desde el before_flush listener)
        if session_instance:
            session_instance.add(log)
        else:
            try:
                db.session.add(log)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error registrando entrada en bitácora: {str(e)}")

        return log