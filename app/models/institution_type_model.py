from app.extensions import db

class InstitutionType(db.Model):
    __tablename__ = 'institution_types'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    institution_type_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Relaciones
    institutions = db.relationship('Institution', back_populates='institution_type', lazy=True)

    def __repr__(self):
        return f'<InstitutionType {self.institution_type_code}: {self.name}>'
