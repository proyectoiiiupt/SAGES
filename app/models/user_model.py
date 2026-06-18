from flask_login import UserMixin
from app.extensions import db
from datetime import datetime, timezone

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    user_code = db.Column(db.String(50), unique=True, nullable=False)
    person_id = db.Column(db.BigInteger, db.ForeignKey('sages.persons.id'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    status_id = db.Column(db.BigInteger, db.ForeignKey('sages.status.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    person = db.relationship('Person', back_populates='user')
    status = db.relationship('Status', back_populates='users')
    roles_assoc = db.relationship('RoleUser', back_populates='user', cascade="all, delete-orphan")
    requests = db.relationship('Request', back_populates='user', lazy=True)
    enabled_services = db.relationship('StateService', back_populates='enabled_by_user', lazy=True)
    logs = db.relationship('Binnacle', back_populates='user', lazy=True)

    def __repr__(self):
        return f"<User {self.user_code}: {self.user_name}>"