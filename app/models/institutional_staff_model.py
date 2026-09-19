from app.extensions import db
from datetime import datetime, timezone
from app.binnacle.mixins import AuditableMixin
from app.binnacle.types import AuditModule

class InstitutionalStaff(db.Model, AuditableMixin):
    __tablename__ = 'institutional_staff'
    __table_args__ = {'schema': 'sages'}
    __audit_module__ = AuditModule.USERS.value

    id = db.Column(db.BigInteger, primary_key=True)
    person_id = db.Column(db.BigInteger, db.ForeignKey('sages.persons.id'), nullable=False)
    institution_id = db.Column(db.BigInteger, db.ForeignKey('sages.institutions.id'), nullable=False)
    position_id = db.Column(db.BigInteger, db.ForeignKey('sages.positions.id'), nullable=False)
    status_id = db.Column(db.BigInteger, db.ForeignKey('sages.status.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    person = db.relationship('Person', back_populates='institutional_staff')
    institution = db.relationship('Institution', back_populates='institutional_staff')
    position = db.relationship('Position', back_populates='institutional_staff')
    status = db.relationship('Status', back_populates='institutional_staff')
    evidences = db.relationship('StaffEvidence', back_populates='institutional_staff', lazy=True, cascade="all, delete-orphan")
    requests = db.relationship('Request', back_populates='institutional_staff', lazy=True)

    def __repr__(self):
        return f'<InstitutionalStaff Person:{self.person_id} Institution:{self.institution_id}>'