from app.extensions import db
from datetime import datetime, timezone

class CompanyStaff(db.Model):
    __tablename__ = 'company_staff'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    person_id = db.Column(db.BigInteger, db.ForeignKey('sages.persons.id'), nullable=False)
    place_id = db.Column(db.BigInteger, db.ForeignKey('sages.places.id'), nullable=False)
    position_id = db.Column(db.BigInteger, db.ForeignKey('sages.positions.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    person = db.relationship('Person', back_populates='company_staff')
    place = db.relationship('Place', back_populates='company_staff')
    position = db.relationship('Position', back_populates='company_staff')

    def __repr__(self):
        return f'<CompanyStaff Person:{self.person_id} Place:{self.place_id}>'
