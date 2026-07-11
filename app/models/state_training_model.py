from app.extensions import db
from datetime import datetime, timezone

class StateTraining(db.Model):
    __tablename__ = 'state_trainings'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    training_id = db.Column(db.BigInteger, db.ForeignKey('sages.trainings.id'), nullable=False)
    state_id = db.Column(db.BigInteger, db.ForeignKey('sages.states.id'), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    training = db.relationship('Training', back_populates='states_trainings')
    state = db.relationship('State', back_populates='states_trainings')

    def __repr__(self):
        return f'<StateTraining Training:{self.training_id} State:{self.state_id}>'
