from app.extensions import db
from datetime import datetime, timezone

class Person(db.Model):
    __tablename__ = 'persons'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    person_code = db.Column(db.String(50), unique=True, nullable=False)
    identification_type = db.Column(db.String(50), nullable=False)
    identification_number = db.Column(db.String(50), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    second_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    user = db.relationship('User', back_populates='person', uselist=False, cascade='all, delete-orphan')
    institutional_staff = db.relationship('InstitutionalStaff', back_populates='person', lazy=True)
    company_staff = db.relationship('CompanyStaff', back_populates='person', lazy=True)

    def __repr__(self):
        return f'<Person {self.person_code}: {self.first_name} {self.last_name}>'