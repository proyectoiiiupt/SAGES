from app.extensions import db
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import JSONB

class Binnacle(db.Model):
    __tablename__ = 'binnacle'
    __table_args__ = (
        db.Index('idx_binnacle_created_at', 'created_at'),
        db.Index('idx_binnacle_module_action', 'module', 'action_type'),
        db.Index('idx_binnacle_user_id', 'user_id'),
        db.Index('idx_binnacle_target_record', 'target_table', 'record_id'),
        db.Index('idx_binnacle_new_values_gin', 'new_values', postgresql_using='gin'),
        db.Index('idx_binnacle_old_values_gin', 'old_values', postgresql_using='gin'),
        {'schema': 'sages'}
    )

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('sages.users.id'), nullable=True) 
    user_identifier = db.Column(db.String(100), nullable=True)
    module = db.Column(db.String(100), nullable=False)
    action_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='EXITOSO')
    target_table = db.Column(db.String(100), nullable=True) 
    record_id = db.Column(db.BigInteger, nullable=True) 
    old_values = db.Column(JSONB, nullable=True)
    new_values = db.Column(JSONB, nullable=True)
    ip_address = db.Column(db.String(100), nullable=False)
    user_agent = db.Column(db.Text, nullable=True)
    session_id = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    user = db.relationship('User', back_populates='logs')

    def __repr__(self):
        return f'<Binnacle {self.action_type} in {self.module}>'