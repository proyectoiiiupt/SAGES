from flask_login import UserMixin
from app.extensions import db
from datetime import datetime, timezone
from app.binnacle.mixins import AuditableMixin
from app.binnacle.types import AuditModule

class User(db.Model, UserMixin, AuditableMixin):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'sages'}
    __audit_module__ = AuditModule.USERS.value

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
    roles_assoc = db.relationship('RoleUser', back_populates='user', cascade='all, delete-orphan')
    logs = db.relationship('Binnacle', back_populates='user', lazy=True)
    request_trackings = db.relationship('RequestTracking', back_populates='user', lazy=True)
    ratings = db.relationship('Rating', back_populates='user', lazy=True)
    attended_requests = db.relationship('Request', back_populates='attended_by', lazy=True)

    def __repr__(self):
        return f'<User {self.user_code}: {self.user_name}>'

    @property
    def permissions(self) -> set:
        perms = set()
        for role_assoc in self.roles_assoc:
            for perm_assoc in role_assoc.role.permissions_assoc:
                if perm_assoc.permission.view:
                    perms.add(perm_assoc.permission.view)
        return perms

    @property
    def full_name(self) -> str:
        if self.person:
            return f"{self.person.first_name or ''} {self.person.last_name or ''}".strip() or self.user_name
        return self.user_name

    @property
    def identifier(self) -> str:
        if self.person and self.person.identification_number:
            return f"{self.person.identification_type}-{self.person.identification_number}"
        return self.user_name

    @property
    def role(self) -> str:
        if self.roles_assoc and len(self.roles_assoc) > 0 and self.roles_assoc[0].role:
            role_map = {
                'super_admin': 'Super Administrador',
                'state_admin': 'Administrador Estadal',
                'applicant': 'Solicitante'
            }
            r_name = self.roles_assoc[0].role.name
            return role_map.get(r_name, r_name)
        return 'Usuario'
