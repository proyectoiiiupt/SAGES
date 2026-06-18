from app.extensions import db

class PermissionRole(db.Model):
    __tablename__ = 'permissions_roles'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    role_id = db.Column(db.BigInteger, db.ForeignKey('sages.roles.id'), nullable=False)
    permission_id = db.Column(db.BigInteger, db.ForeignKey('sages.permissions.id'), nullable=False)

    # Relaciones
    role = db.relationship('Role', back_populates='permissions_assoc')
    permission = db.relationship('Permission', back_populates='roles_assoc')

    def __repr__(self):
        return f"<PermissionRole Role:{self.role_id} Permission:{self.permission_id}>"