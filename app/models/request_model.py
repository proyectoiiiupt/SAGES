from app.extensions import db
from datetime import datetime, timezone

class Request(db.Model):
    __tablename__ = 'requests'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    request_code = db.Column(db.String(50), unique=True, nullable=False)
    institutional_staff_id = db.Column(db.BigInteger, db.ForeignKey('sages.institutional_staff.id'), nullable=False)
    training_id = db.Column(db.BigInteger, db.ForeignKey('sages.trainings.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status_id = db.Column(db.BigInteger, db.ForeignKey('sages.status.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    historical = db.Column(db.Boolean, nullable=False, default=False)

    # Relaciones
    institutional_staff = db.relationship('InstitutionalStaff', back_populates='requests')
    training = db.relationship('Training', back_populates='requests')
    status = db.relationship('Status', back_populates='requests')
    plannings = db.relationship('RequestPlanning', back_populates='request', cascade='all, delete-orphan', lazy=True)
    justifications = db.relationship('RequestJustification', back_populates='request', cascade='all, delete-orphan', lazy=True)
    evidences = db.relationship('Evidence', back_populates='request', cascade='all, delete-orphan', lazy=True)
    tracking_steps = db.relationship('RequestTracking', back_populates='request', cascade='all, delete-orphan', lazy=True)
    ratings = db.relationship('Rating', back_populates='request', cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'<Request {self.request_code}>'