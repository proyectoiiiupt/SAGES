from app.extensions import db
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import JSONB


class Binnacle(db.Model):
    __tablename__ = 'binnacle'
    __table_args__ = {'schema': 'sages'}

    id = db.Column(db.BigInteger, primary_key=True)
    # Cambiado a True: Permite registrar intentos de acceso de usuarios no registrados o fallidos
    user_id = db.Column(db.BigInteger, db.ForeignKey('sages.users.id'), nullable=True) 
    module = db.Column(db.String(100), nullable=False)
    
    # Cambiados a True: Los logs de acceso (visitas, logins) no afectan tablas ni registros
    target_table = db.Column(db.String(100), nullable=True) 
    record_id = db.Column(db.BigInteger, nullable=True) 
    
    action_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    old_values = db.Column(JSONB, nullable=True)
    new_values = db.Column(JSONB, nullable=True)
    ip_address = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    user = db.relationship('User', back_populates='logs')

    def __repr__(self):
        return f'<Binnacle {self.action_type} in {self.module}>'