from app.extensions import db

class TrainingLevel(db.Model):
    __tablename__ = 'training_levels'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    training_id = db.Column(db.BigInteger, db.ForeignKey('sages.trainings.id'), nullable=False)
    educational_level_id = db.Column(db.BigInteger, db.ForeignKey('sages.educational_levels.id'), nullable=False)

    # Relaciones
    training = db.relationship('Training', back_populates='training_levels')
    educational_level = db.relationship('EducationalLevel', back_populates='training_levels')

    def __repr__(self):
        return f'<TrainingLevel Training:{self.training_id} Level:{self.educational_level_id}>'
