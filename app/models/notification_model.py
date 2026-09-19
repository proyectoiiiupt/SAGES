from app.extensions import db
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Index

class Notification(db.Model):
    __tablename__ = 'notifications'
    __table_args__ = (
        Index('idx_notifications_user_unread', 'user_id', 'is_read', 'created_at'),
        Index('idx_notifications_user_history', 'user_id', 'created_at'),
        Index('idx_notifications_extra_data_gin', 'extra_data', postgresql_using='gin'),
        {'schema': 'sages'}
    )

    id = db.Column(db.BigInteger, primary_key=True)
    notification_code = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.BigInteger, db.ForeignKey('sages.users.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(20), nullable=False, default='INFO', server_default='INFO')
    event_code = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    redirect_url = db.Column(db.String(255), nullable=True)
    action_text = db.Column(db.String(80), nullable=True)
    extra_data = db.Column(JSONB, nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', backref=db.backref('notifications', cascade='all, delete-orphan', lazy=True))

    def __repr__(self):
        return f'<Notification {self.notification_code}: {self.title}>'
