from app.extensions import db

class Permission(db.Model):
    __tablename__ = 'permissions'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    permission_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    view = db.Column(db.String(200), nullable=False)

    # Relaciones
    roles_assoc = db.relationship('PermissionRole', back_populates='permission', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Permission {self.name}>'