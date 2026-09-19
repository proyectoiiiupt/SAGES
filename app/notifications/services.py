import uuid
from typing import List
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.notification_model import Notification
from app.models.user_model import User
from app.models.role_model import Role
from app.models.role_user_model import RoleUser
from app.models.institutional_staff_model import InstitutionalStaff
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
            
            notification = Notification(
                notification_code=NotificationService.generate_notification_code(),
                user_id=user_id,
                type=severity_override.value if severity_override else payload["type"],
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
    def notify_role(
        role_name: str,
        event: NotificationEvent,
        context: dict = None,
        state_id: int = None,
        redirect_url: str = None,
        action_text: str = None,
        exclude_user_id: int = None,
        db_session=None
    ) -> List[Notification]:
        """
        Notificación dirigida por rol y ámbito territorial.
        """
        session = db_session or db.session
        try:
            query = session.query(User).join(
                RoleUser, User.id == RoleUser.user_id
            ).join(
                Role, Role.id == RoleUser.role_id
            ).filter(Role.name == role_name)
            
            if exclude_user_id:
                query = query.filter(User.id != exclude_user_id)
                
            users = query.all()
            notifications = []
            
            if not users:
                return []
                
            payload = resolve_notification_payload(event, context)
            
            for user in users:
                notification = Notification(
                    notification_code=NotificationService.generate_notification_code(),
                    user_id=user.id,
                    type=payload["type"],
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
            ).filter(InstitutionalStaff.institution_id == institution_id)
            
            if exclude_user_id:
                query = query.filter(User.id != exclude_user_id)
                
            users = query.all()
            notifications = []
            
            if not users:
                return []
                
            payload = resolve_notification_payload(event, context)
            
            for user in users:
                notification = Notification(
                    notification_code=NotificationService.generate_notification_code(),
                    user_id=user.id,
                    type=payload["type"],
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
