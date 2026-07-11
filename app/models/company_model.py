from app.extensions import db
from datetime import datetime, timezone

class Company(db.Model):
    __tablename__ = 'companies'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    company_code = db.Column(db.String(50), unique=True, nullable=False)
    company_name = db.Column(db.String(200), nullable=False)
    identification_type = db.Column(db.String(50), nullable=False)
    rif = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    places = db.relationship('Place', back_populates='company', lazy=True)

    def __repr__(self):
        return f'<Company {self.company_code}: {self.company_name}>'