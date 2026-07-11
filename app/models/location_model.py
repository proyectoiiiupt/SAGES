from app.extensions import db
from sqlalchemy import UniqueConstraint

class Location(db.Model):
    __tablename__ = 'locations'
    __table_args__ = (
        UniqueConstraint('city_id', 'parish_id', name='unique_coverage'),
        {'schema': 'sages'},
    )

    id = db.Column(db.BigInteger, primary_key=True)
    city_id = db.Column(db.BigInteger, db.ForeignKey('sages.cities.id'), nullable=False)
    parish_id = db.Column(db.BigInteger, db.ForeignKey('sages.parishes.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Relaciones
    city = db.relationship('City', back_populates='locations')
    parish = db.relationship('Parish', back_populates='locations')

    def __repr__(self):
        return f'<Location {self.name}>'
