from app.extensions import db
from datetime import datetime, timezone
from app.binnacle.mixins import AuditableMixin
from app.binnacle.types import AuditModule

class TrainingModule(db.Model, AuditableMixin):
    __tablename__ = 'training_modules'
    __table_args__ = {'schema': 'sages'}
    __audit_module__ = AuditModule.TRAININGS.value
    __audit_exclude_fields__ = {'created_at', 'updated_at'}

    id = db.Column(db.BigInteger, primary_key=True)
    module_code = db.Column(db.String(50), unique=True, nullable=False, index=True) # ej: MOD-001
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), 
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relación 1 a N con Temas Formativos
    trainings = db.relationship('Training', back_populates='training_module', lazy='select', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<TrainingModule {self.module_code}: {self.name}>'
