from app.extensions import db

class EducationalLevel(db.Model):
    __tablename__ = 'educational_levels'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    level_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Relaciones
    institution_levels = db.relationship('InstitutionLevel', back_populates='educational_level', lazy=True)
    training_levels = db.relationship('TrainingLevel', back_populates='educational_level', lazy=True)

    def __repr__(self):
        return f'<EducationalLevel {self.level_code}: {self.name}>'
