from app.extensions import db

class Parish(db.Model):
    __tablename__ = 'parishes'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    municipality_id = db.Column(db.BigInteger, db.ForeignKey('sages.municipalities.id'), nullable=False)
    parish_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Relaciones
    municipality = db.relationship('Municipality', back_populates='parishes')
    locations = db.relationship('Location', back_populates='parish', lazy=True)
    institutions = db.relationship('Institution', back_populates='parish', lazy=True)
    places = db.relationship('Place', back_populates='parish', lazy=True)

    def __repr__(self):
        return f'<Parish {self.name}>'