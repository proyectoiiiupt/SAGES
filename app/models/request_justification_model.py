from app.extensions import db

class RequestJustification(db.Model):
    __tablename__ = 'request_justifications'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    request_id = db.Column(db.BigInteger, db.ForeignKey('sages.requests.id'), nullable=False)
    reason_id = db.Column(db.BigInteger, db.ForeignKey('sages.reasons.id'), nullable=False)
    justification = db.Column(db.Text, nullable=False)

    # Relaciones
    request = db.relationship('Request', back_populates='justifications')
    reason = db.relationship('Reason', back_populates='justifications')

    def __repr__(self):
        return f'<RequestJustification Request:{self.request_id} Reason:{self.reason_id}>'
