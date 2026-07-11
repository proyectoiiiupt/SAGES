from app.extensions import db

class City(db.Model):
    __tablename__ = 'cities'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    state_id = db.Column(db.BigInteger, db.ForeignKey('sages.states.id'), nullable=False)
    city_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_capital = db.Column(db.Boolean, nullable=False, default=False)

    # Relaciones
    state = db.relationship('State', back_populates='cities')
    locations = db.relationship('Location', back_populates='city', lazy=True)

    def __repr__(self):
        return f'<City {self.name}>'
