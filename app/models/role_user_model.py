from app.extensions import db

class RoleUser(db.Model):
    __tablename__ = 'role_users'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('sages.users.id'), nullable=False)
    role_id = db.Column(db.BigInteger, db.ForeignKey('sages.roles.id'), nullable=False)

    # Relaciones
    user = db.relationship('User', back_populates='roles_assoc')
    role = db.relationship('Role', back_populates='users_assoc')

    def __repr__(self):
        return f'<RoleUser User:{self.user_id} Role:{self.role_id}>'