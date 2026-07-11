from app.extensions import db

class InstitutionScope(db.Model):
    __tablename__ = 'institution_scopes'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    scope_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Relaciones
    institutions = db.relationship('Institution', back_populates='institution_scope', lazy=True)

    def __repr__(self):
        return f'<InstitutionScope {self.scope_code}: {self.name}>'
