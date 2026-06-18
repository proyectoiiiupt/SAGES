from app.extensions import db

class Status(db.Model):
    __tablename__ = 'status'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    status_code = db.Column(db.String(50), unique=True, nullable=False)
    status_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    module = db.Column(db.String(200), nullable=False)

    # Relación
    users = db.relationship('User', back_populates='status')
    services = db.relationship('Service', back_populates='status', lazy=True)
    requests = db.relationship('Request', back_populates='status', lazy=True)

    def __repr__(self):
        return f"<Status {self.status_code} - {self.module}: {self.status_name}>"