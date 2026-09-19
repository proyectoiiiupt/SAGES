from app.extensions import db
from datetime import datetime, timezone

class StaffEvidence(db.Model):
    __tablename__ = 'staff_evidences'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    institutional_staff_id = db.Column(db.BigInteger, db.ForeignKey('sages.institutional_staff.id'), nullable=False)
    file_name = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(100), nullable=False)
    format = db.Column(db.String(50), nullable=False)
    file_weight = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    institutional_staff = db.relationship('InstitutionalStaff', back_populates='evidences')

    def __repr__(self):
        return f'<StaffEvidence {self.id} - File: {self.file_name}>'