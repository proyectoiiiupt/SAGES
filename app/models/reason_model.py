from app.extensions import db

class Reason(db.Model):
    __tablename__ = 'reasons'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    reason_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Relaciones
    justifications = db.relationship('RequestJustification', back_populates='reason', lazy=True)

    def __repr__(self):
        return f'<Reason {self.reason_code}: {self.name}>'
