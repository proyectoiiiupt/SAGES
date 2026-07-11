from app.extensions import db
from datetime import datetime, timezone

class Institution(db.Model):
    __tablename__ = 'institutions'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    institution_code = db.Column(db.String(50), unique=True, nullable=False)
    institution_type_id = db.Column(db.BigInteger, db.ForeignKey('sages.institution_types.id'), nullable=False)
    institution_name = db.Column(db.String(200), nullable=False)
    plantel_code = db.Column(db.String(50), unique=True, nullable=False)
    institution_scope_id = db.Column(db.BigInteger, db.ForeignKey('sages.institution_scopes.id'), nullable=False)
    institution_dependency_id = db.Column(db.BigInteger, db.ForeignKey('sages.institution_dependencies.id'), nullable=False)
    parish_id = db.Column(db.BigInteger, db.ForeignKey('sages.parishes.id'), nullable=False)
    address = db.Column(db.Text, nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    status_id = db.Column(db.BigInteger, db.ForeignKey('sages.status.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    institution_type = db.relationship('InstitutionType', back_populates='institutions')
    institution_scope = db.relationship('InstitutionScope', back_populates='institutions')
    institution_dependency = db.relationship('InstitutionDependency', back_populates='institutions')
    parish = db.relationship('Parish', back_populates='institutions')
    status = db.relationship('Status', back_populates='institutions')
    institution_levels = db.relationship('InstitutionLevel', back_populates='institution', cascade='all, delete-orphan', lazy=True)
    institutional_staff = db.relationship('InstitutionalStaff', back_populates='institution', lazy=True)

    def __repr__(self):
        return f'<Institution {self.institution_code}: {self.institution_name}>'
