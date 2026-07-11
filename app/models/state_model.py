from app.extensions import db

class State(db.Model):
    __tablename__ = 'states'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    state_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

    # Relaciones
    cities = db.relationship('City', back_populates='state', lazy=True)
    municipalities = db.relationship('Municipality', back_populates='state', lazy=True)
    states_trainings = db.relationship('StateTraining', back_populates='state', lazy=True)

    def __repr__(self):
        return f'<State {self.name}>'