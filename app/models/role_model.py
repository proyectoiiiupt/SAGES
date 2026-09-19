from app.extensions import db
from app.binnacle.mixins import AuditableMixin
from app.binnacle.types import AuditModule

class Role(db.Model, AuditableMixin):
    __tablename__ = 'roles'
    __table_args__ = {'schema': 'sages'}
    __audit_module__ = AuditModule.CONFIGURATIONS.value

    id = db.Column(db.BigInteger, primary_key=True)
    role_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Relaciones
    users_assoc = db.relationship('RoleUser', back_populates='role', cascade='all, delete-orphan')
    permissions_assoc = db.relationship('PermissionRole', back_populates='role', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Role {self.name}>'