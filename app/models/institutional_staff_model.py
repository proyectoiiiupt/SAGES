from app.extensions import db
from datetime import datetime, timezone

class InstitutionalStaff(db.Model):
    __tablename__ = 'institutional_staff'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    person_id = db.Column(db.BigInteger, db.ForeignKey('sages.persons.id'), nullable=False)
    institution_id = db.Column(db.BigInteger, db.ForeignKey('sages.institutions.id'), nullable=False)
    position_id = db.Column(db.BigInteger, db.ForeignKey('sages.positions.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    person = db.relationship('Person', back_populates='institutional_staff')
    institution = db.relationship('Institution', back_populates='institutional_staff')
    position = db.relationship('Position', back_populates='institutional_staff')
    requests = db.relationship('Request', back_populates='institutional_staff', lazy=True)

    def __repr__(self):
        return f'<InstitutionalStaff Person:{self.person_id} Institution:{self.institution_id}>'
