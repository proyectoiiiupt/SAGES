from app.extensions import db
from datetime import datetime, timezone

class Rating(db.Model):
    __tablename__ = 'ratings'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    request_id = db.Column(db.BigInteger, db.ForeignKey('sages.requests.id'), nullable=False)
    user_id = db.Column(db.BigInteger, db.ForeignKey('sages.users.id'), nullable=False)
    score_activity = db.Column(db.SmallInteger, db.CheckConstraint('score_activity >= 1 AND score_activity <= 5', name='chk_score_activity'), nullable=False)
    score_instructor = db.Column(db.SmallInteger, db.CheckConstraint('score_instructor >= 1 AND score_instructor <= 5', name='chk_score_instructor'), nullable=False)
    score_admin_response = db.Column(db.SmallInteger, db.CheckConstraint('score_admin_response >= 1 AND score_admin_response <= 5', name='chk_score_admin_response'), nullable=False)
    score = db.Column(db.Numeric(4, 2), nullable=False)
    details = db.Column(db.JSON, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    request = db.relationship('Request', back_populates='ratings')
    user = db.relationship('User', back_populates='ratings')

    def __repr__(self):
        return f'<Rating Request:{self.request_id} Score:{self.score}>'
