from app.extensions import db
from datetime import datetime, timezone

class RequestTracking(db.Model):
    __tablename__ = 'request_trackings'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    request_id = db.Column(db.BigInteger, db.ForeignKey('sages.requests.id'), nullable=False)
    user_id = db.Column(db.BigInteger, db.ForeignKey('sages.users.id'), nullable=False)
    messages = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    request = db.relationship('Request', back_populates='tracking_steps')
    user = db.relationship('User', back_populates='request_trackings')

    def __repr__(self):
        return f'<RequestTracking Request:{self.request_id} User:{self.user_id}>'