from app.extensions import db

class InstitutionDependency(db.Model):
    __tablename__ = 'institution_dependencies'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    dependency_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Relaciones
    institutions = db.relationship('Institution', back_populates='institution_dependency', lazy=True)

    def __repr__(self):
        return f'<InstitutionDependency {self.dependency_code}: {self.name}>'
