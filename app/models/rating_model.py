from app.extensions import db
from datetime import datetime, timezone

class Rating(db.Model):
    __tablename__ = 'ratings'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    request_id = db.Column(db.BigInteger, db.ForeignKey('sages.requests.id'), nullable=False)
    user_id = db.Column(db.BigInteger, db.ForeignKey('sages.users.id'), nullable=False)
    score = db.Column(db.SmallInteger, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    request = db.relationship('Request', back_populates='ratings')
    user = db.relationship('User', back_populates='ratings')

    def __repr__(self):
        return f'<Rating Request:{self.request_id} Score:{self.score}>'
