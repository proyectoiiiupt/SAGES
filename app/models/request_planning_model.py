from app.extensions import db
from datetime import datetime, timezone

class RequestPlanning(db.Model):
    __tablename__ = 'request_plannings'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    requests_id = db.Column(db.BigInteger, db.ForeignKey('sages.requests.id'), nullable=False)
    acceptance_deadline = db.Column(db.DateTime(timezone=True), nullable=True)
    accepted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    planned_for = db.Column(db.Date, nullable=True)
    execution_deadline = db.Column(db.DateTime(timezone=True), nullable=True)
    attended = db.Column(db.Boolean, nullable=False, default=False)
    attended_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_exceeded = db.Column(db.Boolean, nullable=False, default=False)
    time_exceeded = db.Column(db.Integer, nullable=True)

    # Relaciones
    request = db.relationship('Request', back_populates='plannings')

    def __repr__(self):
        return f'<RequestPlanning Request:{self.requests_id}>'
