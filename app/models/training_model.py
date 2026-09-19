from app.extensions import db
from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint, func

class Training(db.Model):
    __tablename__ = 'trainings'
    __table_args__ = (
        UniqueConstraint('training_module_id', 'name', name='uq_module_training_name'),
        {'schema': 'sages'},
    )

    id = db.Column(db.BigInteger, primary_key=True)
    training_module_id = db.Column(db.BigInteger, db.ForeignKey('sages.training_modules.id', ondelete='RESTRICT'), nullable=False, index=True)
    training_code = db.Column(db.String(50), unique=True, nullable=False, index=True) # ej: TRN-001
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status_id = db.Column(db.BigInteger, db.ForeignKey('sages.status.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), 
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True) # Soft delete

    # Relaciones
    training_module = db.relationship('TrainingModule', back_populates='trainings')
    status = db.relationship('Status', back_populates='trainings')
    requests = db.relationship('Request', back_populates='training', lazy='dynamic')

    def __repr__(self):
        return f'<Training {self.training_code}: {self.name}>'