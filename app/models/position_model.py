from app.extensions import db

class Position(db.Model):
    __tablename__ = 'positions'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    position_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Relaciones
    institutional_staff = db.relationship('InstitutionalStaff', back_populates='position', lazy=True)
    company_staff = db.relationship('CompanyStaff', back_populates='position', lazy=True)

    def __repr__(self):
        return f'<Position {self.name}>'
