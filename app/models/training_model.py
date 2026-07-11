from app.extensions import db
from datetime import datetime, timezone

class Training(db.Model):
    __tablename__ = 'trainings'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    training_category_id = db.Column(db.BigInteger, db.ForeignKey('sages.training_categories.id'), nullable=False)
    training_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status_id = db.Column(db.BigInteger, db.ForeignKey('sages.status.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relaciones
    training_category = db.relationship('TrainingCategory', back_populates='trainings')
    status = db.relationship('Status', back_populates='trainings')
    training_levels = db.relationship('TrainingLevel', back_populates='training', cascade='all, delete-orphan', lazy=True)
    states_trainings = db.relationship('StateTraining', back_populates='training', lazy=True)
    requests = db.relationship('Request', back_populates='training', lazy=True)

    def __repr__(self):
        return f'<Training {self.name}>'
