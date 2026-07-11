from app.extensions import db
from datetime import datetime, timezone

class Place(db.Model):
    __tablename__ = 'places'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    place_code = db.Column(db.String(50), unique=True, nullable=False)
    company_id = db.Column(db.BigInteger, db.ForeignKey('sages.companies.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    parish_id = db.Column(db.BigInteger, db.ForeignKey('sages.parishes.id'), nullable=False)
    address = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    status_id = db.Column(db.BigInteger, db.ForeignKey('sages.status.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    company = db.relationship('Company', back_populates='places')
    parish = db.relationship('Parish', back_populates='places')
    status = db.relationship('Status', back_populates='places')
    company_staff = db.relationship('CompanyStaff', back_populates='place', lazy=True)

    def __repr__(self):
        return f'<Place {self.place_code}: {self.name}>'
