from app.extensions import db
from datetime import datetime, timezone

class TrainingCategory(db.Model):
    __tablename__ = 'training_categories'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    category_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    trainings = db.relationship('Training', back_populates='training_category', lazy=True)

    def __repr__(self):
        return f'<TrainingCategory {self.name}>'
