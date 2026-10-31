import uuid
from typing import List, Optional
from sqlalchemy import func
from app.extensions import db
from app.models.notification_model import Notification
from app.models.user_model import User
from app.models.role_model import Role
from app.models.role_user_model import RoleUser
from app.models.institutional_staff_model import InstitutionalStaff
from app.models.company_staff_model import CompanyStaff
from app.models.place_model import Place
from app.models.parish_model import Parish
from app.models.municipality_model import Municipality
from app.models.institution_model import Institution
from app.models.person_model import Person
from app.notifications.enums import NotificationEvent, NotificationType
from app.notifications.templates_map import resolve_notification_payload

class NotificationService:
    @staticmethod
    def generate_notification_code() -> str:
        """Genera un código único institucional NOTIF-XXXXXX."""
        short_id = str(uuid.uuid4()).upper()[:6]
        return f"NOTIF-{short_id}"

    @staticmethod
    def notify_user(
        user_id: int,
        event: NotificationEvent,
        context: dict = None,
        redirect_url: str = None,
        action_text: str = None,
        severity_override: NotificationType = None,
        db_session=None
    ) -> Notification:
        """
        Punto único de entrada para generar y persistir una notificación 1-a-1.
        """
        session = db_session or db.session
        
        try:
            payload = resolve_notification_payload(event, context)
            final_type = severity_override.value if severity_override else payload["type"]
            
            notification = Notification(
                notification_code=NotificationService.generate_notification_code(),
                user_id=user_id,
                type=final_type,
                event_code=event.value,
                title=payload["title"],
                message=payload["message"],
                redirect_url=redirect_url,
                action_text=action_text,
                extra_data=context.get("_display", context) if context else None
            )
            
            session.add(notification)
            if not db_session:
                session.commit()
                
            return notification
            
        except Exception as e:
            if not db_session:
                session.rollback()
            raise e

    @staticmethod
    def notify_user_once(
        user_id: int,
        event: NotificationEvent,
        unique_redirect_url: str,
        context: dict = None,
        action_text: str = None,
        severity_override: NotificationType = None,
        only_if_unread: bool = False,
        db_session=None
    ) -> Optional[Notification]:
        """
        Envía una notificación a un usuario SOLO si no existe ya una notificación previa
        con el mismo (user_id, event_code, redirect_url). Ideal para alertas de SLA y bloqueos
        evaluados al cargar bandejas (evita registros duplicados en cada recarga).
        """
        session = db_session or db.session
        query = session.query(Notification).filter_by(
            user_id=user_id,
            event_code=event.value,
            redirect_url=unique_redirect_url
        )
        if only_if_unread:
            query = query.filter_by(is_read=False)

        if query.first() is not None:
            return None

        return NotificationService.notify_user(
            user_id=user_id,
            event=event,
            context=context,
            redirect_url=unique_redirect_url,
            action_text=action_text,
            severity_override=severity_override,
            db_session=db_session
        )

    @staticmethod
    def notify_role(
        role_name: str,
        event: NotificationEvent,
        context: dict = None,
        state_id: int = None,
        redirect_url: str = None,
        action_text: str = None,
        exclude_user_id: int = None,
        severity_override: NotificationType = None,
        db_session=None
    ) -> List[Notification]:
        """
        Notificación dirigida por rol y ámbito territorial.
        Filtra cuentas activas (User.status_id == 1). Si se provee state_id, resuelve
        geográficamente a los state_admin por sede o a los applicant por institución.
        """
        session = db_session or db.session
        try:
            query = session.query(User).join(
                RoleUser, User.id == RoleUser.user_id
            ).join(
                Role, Role.id == RoleUser.role_id
            ).filter(
                func.lower(Role.name) == role_name.lower(),
                User.status_id == 1
            )
            
            if exclude_user_id:
                query = query.filter(User.id != exclude_user_id)

            if state_id is not None:
                if role_name.lower() == 'state_admin':
                    query = (
                        query.join(Person, User.person_id == Person.id)
                        .join(CompanyStaff, Person.id == CompanyStaff.person_id)
                        .join(Place, CompanyStaff.place_id == Place.id)
                        .join(Parish, Place.parish_id == Parish.id)
                        .join(Municipality, Parish.municipality_id == Municipality.id)
                        .filter(
                            CompanyStaff.status_id == 1,
                            Municipality.state_id == state_id
                        )
                    )
                elif role_name.lower() == 'applicant':
                    query = (
                        query.join(Person, User.person_id == Person.id)
                        .join(InstitutionalStaff, Person.id == InstitutionalStaff.person_id)
                        .join(Institution, InstitutionalStaff.institution_id == Institution.id)
                        .join(Parish, Institution.parish_id == Parish.id)
                        .join(Municipality, Parish.municipality_id == Municipality.id)
                        .filter(Municipality.state_id == state_id)
                    )
                
            users = query.distinct().all()
            notifications = []
            
            if not users:
                return []
                
            payload = resolve_notification_payload(event, context)
            final_type = severity_override.value if severity_override else payload["type"]
            
            for user in users:
                notification = Notification(
                    notification_code=NotificationService.generate_notification_code(),
                    user_id=user.id,
                    type=final_type,
                    event_code=event.value,
                    title=payload["title"],
                    message=payload["message"],
                    redirect_url=redirect_url,
                    action_text=action_text,
                    extra_data=context.get("_display", context) if context else None
                )
                session.add(notification)
                notifications.append(notification)
                
            if not db_session:
                session.commit()
                
            return notifications
        except Exception as e:
            if not db_session:
                session.rollback()
            raise e

    @staticmethod
    def notify_institution_affiliates(
        institution_id: int,
        event: NotificationEvent,
        context: dict = None,
        exclude_user_id: int = None,
        redirect_url: str = None,
        action_text: str = None,
        severity_override: NotificationType = None,
        db_session=None
    ) -> List[Notification]:
        """
        Notifica a todo el personal institucional con cuenta activa en un plantel determinado.
        """
        session = db_session or db.session
        try:
            query = session.query(User).join(
                Person, User.person_id == Person.id
            ).join(
                InstitutionalStaff, InstitutionalStaff.person_id == Person.id
            ).filter(
                InstitutionalStaff.institution_id == institution_id,
                User.status_id == 1
            )
            
            if exclude_user_id:
                query = query.filter(User.id != exclude_user_id)
                
            users = query.distinct().all()
            notifications = []
            
            if not users:
                return []
                
            payload = resolve_notification_payload(event, context)
            final_type = severity_override.value if severity_override else payload["type"]
            
            for user in users:
                notification = Notification(
                    notification_code=NotificationService.generate_notification_code(),
                    user_id=user.id,
                    type=final_type,
                    event_code=event.value,
                    title=payload["title"],
                    message=payload["message"],
                    redirect_url=redirect_url,
                    action_text=action_text,
                    extra_data=context.get("_display", context) if context else None
                )
                session.add(notification)
                notifications.append(notification)
                
            if not db_session:
                session.commit()
                
            return notifications
        except Exception as e:
            if not db_session:
                session.rollback()
            raise e

    @staticmethod
    def notify_place_staff(
        place_id: int,
        event: NotificationEvent,
        context: dict = None,
        exclude_user_id: int = None,
        redirect_url: str = None,
        action_text: str = None,
        severity_override: NotificationType = None,
        db_session=None
    ) -> List[Notification]:
        """
        Notifica a todos los usuarios activos del personal de CORPOELEC adscritos a una sede operativa (Place).
        """
        session = db_session or db.session
        try:
            query = session.query(User).join(
                Person, User.person_id == Person.id
            ).join(
                CompanyStaff, CompanyStaff.person_id == Person.id
            ).filter(
                CompanyStaff.place_id == place_id,
                CompanyStaff.status_id == 1,
                User.status_id == 1
            )

            if exclude_user_id:
                query = query.filter(User.id != exclude_user_id)

            users = query.distinct().all()
            notifications = []

            if not users:
                return []

            payload = resolve_notification_payload(event, context)
            final_type = severity_override.value if severity_override else payload["type"]

            for user in users:
                notification = Notification(
                    notification_code=NotificationService.generate_notification_code(),
                    user_id=user.id,
                    type=final_type,
                    event_code=event.value,
                    title=payload["title"],
                    message=payload["message"],
                    redirect_url=redirect_url,
                    action_text=action_text,
                    extra_data=context.get("_display", context) if context else None
                )
                session.add(notification)
                notifications.append(notification)

            if not db_session:
                session.commit()

            return notifications
        except Exception as e:
            if not db_session:
                session.rollback()
            raise e
