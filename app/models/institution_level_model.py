from app.extensions import db

class InstitutionLevel(db.Model):
    __tablename__ = 'institution_levels'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    institution_id = db.Column(db.BigInteger, db.ForeignKey('sages.institutions.id'), nullable=False)
    educational_level_id = db.Column(db.BigInteger, db.ForeignKey('sages.educational_levels.id'), nullable=False)

    # Relaciones
    institution = db.relationship('Institution', back_populates='institution_levels')
    educational_level = db.relationship('EducationalLevel', back_populates='institution_levels')

    def __repr__(self):
        return f'<InstitutionLevel Institution:{self.institution_id} Level:{self.educational_level_id}>'
