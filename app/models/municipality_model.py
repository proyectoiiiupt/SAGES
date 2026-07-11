from app.extensions import db

class Municipality(db.Model):
    __tablename__ = 'municipalities'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    state_id = db.Column(db.BigInteger, db.ForeignKey('sages.states.id'), nullable=False)
    municipality_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Relaciones
    state = db.relationship('State', back_populates='municipalities')
    parishes = db.relationship('Parish', back_populates='municipality', lazy=True)

    def __repr__(self):
        return f'<Municipality {self.name}>'