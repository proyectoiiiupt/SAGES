from app.extensions import db
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import JSONB

class Binnacle(db.Model):
    __tablename__ = 'binnacle'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('sages.users.id'), nullable=False)
    module = db.Column(db.String(100), nullable=False)
    action_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    old_values = db.Column(JSONB, nullable=True)
    new_values = db.Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    user = db.relationship('User', back_populates='logs')

    def __repr__(self):
        return f'<Binnacle {self.action_type} in {self.module}>'